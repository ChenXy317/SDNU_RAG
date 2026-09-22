from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    database_url: str
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_public_collection: str = "sdnu_public"
    qdrant_private_collection: str = "sdnu_private"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_embedding_model: str = "qwen3-embedding:0.6b"
    ollama_embedding_dim: int = 1024
    ollama_chat_model: str = "qwen2.5:1.5b"
    chat_base_url: str = ""
    chat_api_key: str = ""
    jwt_secret: str
    jwt_expire_hours: int = 12
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def upload_root(self) -> Path:
        return _BACKEND_DIR / "data" / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
