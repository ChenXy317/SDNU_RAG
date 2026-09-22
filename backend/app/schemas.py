import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class AuthRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def email_ok(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("邮箱格式非法")
        return value

    @field_validator("password")
    @classmethod
    def password_ok(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("密码短于 8")
        if len(value.encode("utf-8")) > 72:
            raise ValueError("密码最长 72 字节")
        return value


class UserOut(BaseModel):
    id: str
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class DocumentOut(BaseModel):
    id: str
    filename: str
    status: str
    chunk_count: int
    created_at: datetime
    error_message: str | None = None


class DocumentList(BaseModel):
    items: list[DocumentOut]


class SessionOut(BaseModel):
    id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class SessionList(BaseModel):
    items: list[SessionOut]


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    citations: list[dict] | None = None
    created_at: datetime


class SessionDetail(SessionOut):
    messages: list[MessageOut]


class LLMConfigUpdate(BaseModel):
    base_url: str = Field(min_length=1, max_length=512)
    model: str = Field(min_length=1, max_length=192)
    api_key: str | None = Field(default=None, max_length=512)


class LLMConfigOut(BaseModel):
    base_url: str
    model: str
    api_key_set: bool
    embedding_model: str
    local_models: list[str]


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def message_ok(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("消息不能为空")
        return value
