"""把 knowledge/sdnu 幂等灌入公共集合。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import func, select  # noqa: E402

from app.auth import ensure_public_user  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.ingest import ingest_document  # noqa: E402
from app.models import PUBLIC_USER_ID, Document  # noqa: E402
from app.qdrant_client import delete_document_points, ensure_collections, get_client  # noqa: E402

settings = get_settings()


def main() -> None:
    init_db()
    ensure_collections()
    knowledge = ROOT / "knowledge" / "sdnu"
    files = sorted(path for path in knowledge.glob("*.txt") if path.is_file())
    names = {path.name for path in files}
    with SessionLocal() as db:
        ensure_public_user(db)
        for path in files:
            text = path.read_text(encoding="utf-8-sig")
            doc = ingest_document(
                db,
                user_id=PUBLIC_USER_ID,
                filename=path.name,
                text=text,
                storage_path=str(path),
                collection=settings.qdrant_public_collection,
                source="public",
            )
            print(f"ok {path.name} chunks={doc.chunk_count}", flush=True)
        stale = db.scalars(select(Document).where(Document.user_id == PUBLIC_USER_ID)).all()
        for row in stale:
            if row.filename not in names:
                print(f"警告: {row.filename} 已不在目录中，删除对应记录", flush=True)
                delete_document_points(settings.qdrant_public_collection, row.id)
                db.delete(row)
        db.commit()
        doc_count = db.scalar(
            select(func.count()).select_from(Document).where(Document.user_id == PUBLIC_USER_ID)
        )
    point_count = get_client().count(settings.qdrant_public_collection, exact=True).count
    print(f"txt={len(files)} documents={doc_count} points={point_count}", flush=True)
    if doc_count != len(files):
        raise SystemExit("公共文档数与 txt 数量不一致")


if __name__ == "__main__":
    main()
