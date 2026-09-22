import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.deps import CurrentUserDep, DbDep
from app.models import PUBLIC_USER_EMAIL, PUBLIC_USER_ID, User, utcnow
from app.schemas import AuthRequest, TokenResponse, UserOut

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


def hash_password(password: str) -> str:
    digest = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return digest.decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    if isinstance(token, bytes):
        return token.decode("ascii")
    return token


def ensure_public_user(db) -> User:
    # 公共语料的归属账号，密码是随机哈希，不对外签发登录令牌
    row = db.get(User, PUBLIC_USER_ID)
    if row is not None:
        return row
    row = User(
        id=PUBLIC_USER_ID,
        email=PUBLIC_USER_EMAIL,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        created_at=utcnow(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.scalar(select(User).where(User.email == PUBLIC_USER_EMAIL))
        if row is None:
            raise
    return row


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.email),
        user=UserOut(id=user.id, email=user.email),
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: AuthRequest, db: DbDep) -> TokenResponse:
    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        password_hash=hash_password(body.password),
        created_at=utcnow(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="邮箱已存在") from exc
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(body: AuthRequest, db: DbDep) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUserDep, db: DbDep) -> UserOut:
    row = db.get(User, user.id)
    if row is None:
        raise HTTPException(status_code=401, detail="未登录")
    return UserOut(id=row.id, email=row.email)
