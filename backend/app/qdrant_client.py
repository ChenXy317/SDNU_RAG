import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 点 id 的 UUID5 命名空间。同一用户、文件名、序号始终对应同一个 point。
POINT_NAMESPACE = uuid.UUID("8f3c2b1a-6d4e-5f70-9a8b-1c2d3e4f5061")

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url, timeout=60)
    return _client


def point_id(user_id: str, filename: str, chunk_index: int) -> str:
    return str(uuid.uuid5(POINT_NAMESPACE, f"{user_id}:{filename}:{chunk_index}"))


def _vector_size(vectors) -> int | None:
    if hasattr(vectors, "size"):
        return int(vectors.size)
    return None


def ensure_collections() -> None:
    client = get_client()
    dim = settings.ollama_embedding_dim
    for name in (settings.qdrant_public_collection, settings.qdrant_private_collection):
        if not client.collection_exists(name):
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                metadata={"embedding_model": settings.ollama_embedding_model},
            )
        info = client.get_collection(name)
        size = _vector_size(info.config.params.vectors)
        if size is not None and size != dim:
            logger.warning("集合 %s 维数是 %s，配置是 %s", name, size, dim)
        indexed = set(info.payload_schema or {})
        for field in ("user_id", "document_id"):
            if field not in indexed:
                client.create_payload_index(
                    collection_name=name,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
    logger.info(
        "Qdrant 集合已就绪，embedding 模型 %s",
        settings.ollama_embedding_model,
    )


def delete_document_points(collection: str, document_id: str, user_id: str | None = None) -> None:
    must = [FieldCondition(key="document_id", match=MatchValue(value=document_id))]
    if user_id is not None:
        must.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
    get_client().delete(
        collection_name=collection,
        points_selector=Filter(must=must),
        wait=True,
    )


def upsert_chunks(
    collection: str,
    user_id: str,
    document_id: str,
    filename: str,
    chunks: list[str],
    vectors: list[list[float]],
    source: str,
) -> None:
    points = [
        PointStruct(
            id=point_id(user_id, filename, index),
            vector=vector,
            payload={
                "user_id": user_id,
                "document_id": document_id,
                "filename": filename,
                "chunk_index": index,
                "text": text,
                "source": source,
            },
        )
        for index, (text, vector) in enumerate(zip(chunks, vectors, strict=True))
    ]
    if points:
        get_client().upsert(collection_name=collection, points=points, wait=True)


def search(
    collection: str,
    vector: list[float],
    k: int = 5,
    user_id: str | None = None,
) -> list[dict]:
    if collection == settings.qdrant_private_collection and not user_id:
        raise ValueError("私有检索必须提供 user_id")
    query_filter = None
    if user_id is not None:
        query_filter = Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        )
    response = get_client().query_points(
        collection_name=collection,
        query=vector,
        query_filter=query_filter,
        limit=k,
        with_payload=True,
    )
    rows = []
    for point in response.points:
        payload = point.payload or {}
        rows.append(
            {
                "score": float(point.score or 0),
                "user_id": str(payload.get("user_id") or ""),
                "document_id": str(payload.get("document_id") or ""),
                "filename": str(payload.get("filename") or ""),
                "chunk_index": int(payload.get("chunk_index") or 0),
                "text": str(payload.get("text") or ""),
                "source": str(payload.get("source") or ""),
            }
        )
    return rows


def search_public(vector: list[float], k: int = 5) -> list[dict]:
    return search(settings.qdrant_public_collection, vector, k=k)


def search_private(vector: list[float], user_id: str, k: int = 5) -> list[dict]:
    if not user_id:
        raise ValueError("私有检索必须提供 user_id")
    return search(settings.qdrant_private_collection, vector, k=k, user_id=user_id)
