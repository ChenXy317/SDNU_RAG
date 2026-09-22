import uuid
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm import embed_texts
from app.models import Document, utcnow
from app.qdrant_client import delete_document_points, upsert_chunks

settings = get_settings()


def split_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=320,
        chunk_overlap=48,
        separators=["\n【", "\n## ", "\n\n", "。", "\n", ""],
    )
    chunks: list[str] = []
    for piece in splitter.split_text(text):
        cleaned = piece.strip()
        if len(cleaned) >= 20:
            chunks.append(cleaned)
    return chunks


def ingest_document(
    db: Session,
    *,
    user_id: str,
    filename: str,
    text: str,
    storage_path: str,
    collection: str,
    source: str,
) -> Document:
    filename = Path(filename).name
    doc = db.scalar(
        select(Document).where(Document.user_id == user_id, Document.filename == filename)
    )
    now = utcnow()
    if doc is None:
        doc = Document(
            id=str(uuid.uuid4()),
            user_id=user_id,
            filename=filename,
            storage_path=storage_path,
            status="processing",
            chunk_count=0,
            created_at=now,
            updated_at=now,
        )
        db.add(doc)
    else:
        doc.status = "processing"
        doc.error_message = None
        doc.storage_path = storage_path
        doc.updated_at = now
    db.commit()

    try:
        chunks = split_text(text)
        if not chunks:
            raise ValueError("没有足够长的文本块")
        vectors = embed_texts(chunks)
        owner_filter = user_id if source == "user" else None
        delete_document_points(collection, doc.id, owner_filter)
        upsert_chunks(collection, user_id, doc.id, filename, chunks, vectors, source)
        doc.status = "succeeded"
        doc.chunk_count = len(chunks)
        doc.error_message = None
        doc.updated_at = utcnow()
        db.commit()
        return doc
    except Exception as exc:
        doc.status = "failed"
        doc.error_message = str(exc)[:2000]
        doc.updated_at = utcnow()
        db.commit()
        raise
