from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db

settings = get_settings()


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(token.strip(), settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="未登录") from exc
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    return CurrentUser(id=str(user_id), email=str(payload.get("email") or ""))


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
DbDep = Annotated[Session, Depends(get_db)]
