import logging
from dataclasses import dataclass

from app.config import get_settings
from app.llm import embed_texts
from app.qdrant_client import search_private, search_public

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class Hit:
    filename: str
    chunk_index: int
    text: str
    score: float
    source: str
    document_id: str
    user_id: str


def _hit(row: dict, source: str) -> Hit:
    return Hit(
        filename=row["filename"],
        chunk_index=row["chunk_index"],
        text=row["text"],
        score=row["score"],
        source=source,
        document_id=row["document_id"],
        user_id=row["user_id"],
    )


def merge_hits(public_hits: list[Hit], private_hits: list[Hit], k: int = 5) -> list[Hit]:
    ranked: list[Hit] = []
    seen: set[tuple[str, int]] = set()
    ordered = sorted(public_hits + private_hits, key=lambda item: item.score, reverse=True)
    for hit in ordered:
        key = (hit.document_id, hit.chunk_index)
        if key in seen:
            continue
        seen.add(key)
        ranked.append(hit)
    top = ranked[:k]
    if private_hits and not any(hit.source == "user" for hit in top):
        if len(top) >= k:
            lowest = min(hit.score for hit in top)
            for index, hit in enumerate(top):
                if hit.score == lowest:
                    top = top[:index] + top[index + 1 :]
                    break
        forced = private_hits[0]
        forced_key = (forced.document_id, forced.chunk_index)
        if all((hit.document_id, hit.chunk_index) != forced_key for hit in top):
            top.append(forced)
    return top[:k]


def retrieve(question: str, user_id: str) -> list[Hit]:
    if not user_id:
        raise ValueError("私有检索必须提供 user_id")
    logger.info("查询 embedding 模型 %s", settings.ollama_embedding_model)
    vector = embed_texts([question])[0]
    public_hits = [_hit(row, "public") for row in search_public(vector, k=5)]
    private_hits: list[Hit] = []
    for row in search_private(vector, user_id, k=5):
        if row["user_id"] != user_id:
            logger.warning("丢弃私有命中：payload.user_id 与当前用户不一致")
            continue
        private_hits.append(_hit(row, "user"))
    private_hits.sort(key=lambda item: item.score, reverse=True)
    return merge_hits(public_hits, private_hits)
