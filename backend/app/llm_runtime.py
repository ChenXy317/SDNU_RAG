"""当前账号的对话模型覆盖。重启进程后回到环境变量。"""

import ipaddress
from dataclasses import dataclass
from threading import Lock
from urllib.parse import urlparse

from app.config import get_settings

_ALLOWED_LLM_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "host.docker.internal"})
_BLOCKED_LLM_HOSTS = frozenset(
    {
        "postgres",
        "mysql",
        "redis",
        "qdrant",
        "backend",
        "frontend",
        "metadata.google.internal",
        "metadata.google.com",
        "169.254.169.254",
    }
)


@dataclass
class LLMRuntimeConfig:
    base_url: str
    api_key: str | None
    model: str


_lock = Lock()
_overrides: dict[str, LLMRuntimeConfig] = {}


def env_chat_config() -> LLMRuntimeConfig:
    settings = get_settings()
    base = settings.chat_base_url.strip()
    if not base:
        base = settings.ollama_base_url.rstrip("/") + "/v1"
    key = settings.chat_api_key.strip() or None
    return LLMRuntimeConfig(
        base_url=base.rstrip("/"),
        api_key=key,
        model=settings.ollama_chat_model.strip(),
    )


def _host_blocked(host: str) -> bool:
    host = host.strip().lower().rstrip(".")
    if host in _ALLOWED_LLM_HOSTS:
        return False
    if host in _BLOCKED_LLM_HOSTS:
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return "." not in host
    if addr.is_loopback:
        return False
    return bool(
        addr.is_private
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def validate_llm_base_url(url: str) -> str:
    """只接受公网或本机回环的 http(s) 地址，拒绝内网和云元数据。"""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url 必须是带主机名的 http(s) 地址")
    host = parsed.hostname or ""
    if not host or _host_blocked(host):
        raise ValueError("base_url 主机不允许")
    return url.strip().rstrip("/")


def get_llm_config(user_id: str | None = None) -> LLMRuntimeConfig:
    env = env_chat_config()
    if not user_id:
        return env
    with _lock:
        override = _overrides.get(user_id)
    if override is None:
        return env
    return LLMRuntimeConfig(
        base_url=override.base_url,
        api_key=override.api_key,
        model=override.model,
    )


def set_llm_config(
    *,
    user_id: str,
    base_url: str,
    model: str,
    api_key: str | None = None,
) -> LLMRuntimeConfig:
    if not user_id:
        raise ValueError("需要当前用户")
    env = env_chat_config()
    current = get_llm_config(user_id)
    new_url = validate_llm_base_url(base_url or current.base_url)
    new_model = (model or current.model).strip()
    if not new_model:
        raise ValueError("需要填写模型名")

    if api_key is not None and api_key.strip() == "":
        key = None
    elif api_key is not None:
        key = api_key
    else:
        key = current.api_key
        env_key = (env.api_key or "").strip()
        if new_url != current.base_url and (key or "").strip() == env_key:
            key = None

    cfg = LLMRuntimeConfig(base_url=new_url, api_key=key, model=new_model)
    with _lock:
        _overrides[user_id] = cfg
    return cfg


def clear_llm_overrides() -> None:
    with _lock:
        _overrides.clear()


def effective_api_key(cfg: LLMRuntimeConfig | None = None) -> str:
    current = cfg or get_llm_config()
    key = (current.api_key or "").strip()
    return key if key else "sk-no-auth"
