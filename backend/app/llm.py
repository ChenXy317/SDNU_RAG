import httpx

from app.config import get_settings

settings = get_settings()
EMBED_BATCH = 16


def embed_texts(texts: list[str]) -> list[list[float]]:
    """入库和查询共用的 embedding。返回向量维数必须与配置一致。"""
    if not texts:
        return []
    url = settings.ollama_base_url.rstrip("/") + "/api/embed"
    embeddings: list[list[float]] = []
    with httpx.Client(timeout=180) as client:
        for start in range(0, len(texts), EMBED_BATCH):
            batch = texts[start : start + EMBED_BATCH]
            response = client.post(
                url,
                json={"model": settings.ollama_embedding_model, "input": batch},
            )
            response.raise_for_status()
            vectors = response.json().get("embeddings")
            if not isinstance(vectors, list) or len(vectors) != len(batch):
                raise RuntimeError("embedding 返回数量与输入不一致")
            for vector in vectors:
                if len(vector) != settings.ollama_embedding_dim:
                    raise RuntimeError(
                        f"embedding 维数应为 {settings.ollama_embedding_dim}，实际 {len(vector)}"
                    )
                embeddings.append(vector)
    return embeddings
