import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.db import SessionLocal
from app.deps import CurrentUserDep, DbDep
from app.models import ChatMessage, ChatSession, utcnow
from app.rag import format_context, stream_answer
from app.retrieve import retrieve
from app.schemas import ChatRequest, MessageOut, SessionDetail, SessionList, SessionOut

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


def sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _citations(raw: str | None) -> list[dict] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


def _session_out(row: ChatSession) -> SessionOut:
    return SessionOut(
        id=row.id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _own_session(db, session_id: str, user_id: str) -> ChatSession:
    row = db.scalar(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return row


def _recent_history(db, session_id: str, user_id: str, current_question: str) -> list[tuple[str, str]]:
    """当前会话最近 20 轮对话，不含本次提问。"""
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id, ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(41)
    ).all()
    items = [(row.role, row.content) for row in reversed(rows)]
    if items and items[-1][0] == "user" and items[-1][1] == current_question:
        items = items[:-1]
    return items[-40:]


@router.get("/sessions", response_model=SessionList)
def list_sessions(user: CurrentUserDep, db: DbDep) -> SessionList:
    rows = db.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
    ).all()
    return SessionList(items=[_session_out(row) for row in rows])


@router.post("/sessions", response_model=SessionOut)
def create_session(user: CurrentUserDep, db: DbDep) -> SessionOut:
    now = utcnow()
    row = ChatSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title=None,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    return _session_out(row)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: str, user: CurrentUserDep, db: DbDep) -> SessionDetail:
    row = _own_session(db, session_id, user.id)
    messages = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == row.id, ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    ).all()
    return SessionDetail(
        id=row.id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
        messages=[
            MessageOut(
                id=item.id,
                role=item.role,
                content=item.content,
                citations=_citations(item.citations_json),
                created_at=item.created_at,
            )
            for item in messages
        ],
    )


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, user: CurrentUserDep, db: DbDep) -> None:
    row = _own_session(db, session_id, user.id)
    db.delete(row)
    db.commit()


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, user: CurrentUserDep, db: DbDep):
    session = _own_session(db, body.session_id, user.id)
    now = utcnow()
    db.add(
        ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session.id,
            user_id=user.id,
            role="user",
            content=body.message,
            created_at=now,
        )
    )
    if not session.title:
        session.title = body.message[:40]
    session.updated_at = now
    db.commit()

    session_id = session.id
    user_id = user.id
    question = body.message
    history = _recent_history(db, session_id, user_id, question)

    try:
        hits = retrieve(question, user_id)
    except Exception as exc:
        logger.exception("检索失败")

        async def failed():
            yield sse("error", {"detail": str(exc)})

        return StreamingResponse(failed(), media_type="text/event-stream")

    citations = [
        {
            "filename": hit.filename,
            "chunk_index": hit.chunk_index,
            "text": hit.text,
            "score": hit.score,
            "source": hit.source,
        }
        for hit in hits
    ]
    context = format_context(hits)

    async def events():
        for item in citations:
            yield sse("citation", item)
        parts: list[str] = []
        try:
            async for text in stream_answer(context, question, user_id, history):
                parts.append(text)
                yield sse("token", {"text": text})
            answer = "".join(parts)
            message_id = str(uuid.uuid4())
            with SessionLocal() as write_db:
                write_db.add(
                    ChatMessage(
                        id=message_id,
                        session_id=session_id,
                        user_id=user_id,
                        role="assistant",
                        content=answer,
                        citations_json=json.dumps(citations, ensure_ascii=False),
                        created_at=utcnow(),
                    )
                )
                saved = write_db.get(ChatSession, session_id)
                if saved is not None:
                    saved.updated_at = utcnow()
                write_db.commit()
            yield sse("done", {"message_id": message_id, "answer": answer})
        except Exception as exc:
            logger.exception("生成失败")
            yield sse("error", {"detail": str(exc)})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
