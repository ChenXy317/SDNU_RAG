"""读取和更新当前账号的对话模型。向量模型不在这里改。"""

import logging

import httpx
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.deps import CurrentUserDep
from app.llm_runtime import get_llm_config, set_llm_config
from app.schemas import LLMConfigOut, LLMConfigUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/llm", tags=["llm"])
settings = get_settings()


def list_local_models() -> list[str]:
    url = settings.ollama_base_url.rstrip("/") + "/api/tags"
    try:
        with httpx.Client(timeout=3) as client:
            response = client.get(url)
            response.raise_for_status()
            models = response.json().get("models") or []
    except Exception:
        logger.info("读取本机 Ollama 模型列表失败")
        return []
    names: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _to_out(user_id: str) -> LLMConfigOut:
    cfg = get_llm_config(user_id)
    return LLMConfigOut(
        base_url=cfg.base_url,
        model=cfg.model,
        api_key_set=bool((cfg.api_key or "").strip()),
        embedding_model=settings.ollama_embedding_model,
        local_models=list_local_models(),
    )


@router.get("/config", response_model=LLMConfigOut)
def read_llm_config(user: CurrentUserDep) -> LLMConfigOut:
    return _to_out(user.id)


@router.put("/config", response_model=LLMConfigOut)
def update_llm_config(body: LLMConfigUpdate, user: CurrentUserDep) -> LLMConfigOut:
    try:
        set_llm_config(
            user_id=user.id,
            base_url=body.base_url,
            model=body.model,
            api_key=body.api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("用户 %s 更新对话模型 %s @ %s", user.id, body.model.strip(), body.base_url.strip())
    return _to_out(user.id)
