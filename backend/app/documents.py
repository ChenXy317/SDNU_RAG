from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import select

from app.config import get_settings
from app.deps import CurrentUserDep, DbDep
from app.ingest import ingest_document
from app.models import Document
from app.schemas import DocumentList, DocumentOut

settings = get_settings()
router = APIRouter(tags=["documents"])


def _out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        status=doc.status,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
        error_message=doc.error_message,
    )


@router.get("/documents", response_model=DocumentList)
def list_documents(user: CurrentUserDep, db: DbDep) -> DocumentList:
    rows = db.scalars(
        select(Document)
        .where(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
    ).all()
    return DocumentList(items=[_out(row) for row in rows])


@router.post("/ingest", response_model=DocumentOut)
async def ingest_file(
    user: CurrentUserDep,
    db: DbDep,
    file: UploadFile = File(...),
) -> DocumentOut:
    filename = Path(file.filename or "").name
    if not filename or filename in {".", ".."} or not filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="第一版只接收 .txt")
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="仅支持 UTF-8 编码的 txt") from exc
    dest_dir = settings.upload_root / user.id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_text(text, encoding="utf-8")
    try:
        doc = ingest_document(
            db,
            user_id=user.id,
            filename=filename,
            text=text,
            storage_path=str(dest),
            collection=settings.qdrant_private_collection,
            source="user",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _out(doc)
