import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import ensure_public_user, router as auth_router
from app.chat import router as chat_router
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.documents import router as documents_router
from app.llm_config import router as llm_router
from app.qdrant_client import ensure_collections

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    init_db()
    ensure_collections()
    with SessionLocal() as db:
        ensure_public_user(db)
    logger.info(
        "服务就绪，embedding 模型 %s，维数 %s",
        settings.ollama_embedding_model,
        settings.ollama_embedding_dim,
    )
    yield


app = FastAPI(title="山师大知识库 RAG", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(llm_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
