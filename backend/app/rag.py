from collections.abc import AsyncIterator, Sequence

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from app.llm_runtime import effective_api_key, get_llm_config
from app.retrieve import Hit

SYSTEM_PROMPT = """你是山东师范大学校园知识助手。结合对话历史理解指代，回答只根据本次提供的 Context。
Context 不足时明确说没有找到相关信息，不要编造。
中文提问用中文回答。可在答案中点出文件名。
Context 中同时出现[来源:公共]与[来源:用户]且内容不一致时，必须同时列出两边的说法，并明确指出存在冲突，不要只采用其中一方。"""

MAX_HISTORY_ROUNDS = 20
HISTORY_CHAR_BUDGET = 12000


def format_context(hits: list[Hit]) -> str:
    blocks: list[str] = []
    for hit in hits:
        label = "公共" if hit.source == "public" else "用户"
        blocks.append(f"[来源:{label}] 文件:{hit.filename}\n{hit.text}")
    return "\n\n".join(blocks)


def build_chain(user_id: str):
    cfg = get_llm_config(user_id)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history", optional=True),
            ("user", "Context:\n{context}\n\nQuestion: {question}"),
        ]
    )
    llm = ChatOpenAI(
        model=cfg.model,
        api_key=effective_api_key(cfg),
        base_url=cfg.base_url,
        temperature=0.7,
        max_tokens=2048,
        timeout=300,
        streaming=True,
    )
    return prompt | llm


def normalize_history(raw: Sequence[tuple[str, str]]) -> list:
    """取最近 20 轮对话，超长时从旧到新丢弃。"""
    items = [(role, (text or "").strip()) for role, text in raw if (text or "").strip()]
    items = items[-(MAX_HISTORY_ROUNDS * 2) :]
    total = sum(len(text) for _, text in items)
    while len(items) > 2 and total > HISTORY_CHAR_BUDGET:
        total -= len(items[0][1])
        items = items[1:]
    messages: list = []
    for role, text in items:
        if role == "assistant":
            messages.append(AIMessage(content=text))
        else:
            messages.append(HumanMessage(content=text))
    return messages


def _chunk_text(chunk) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
        return "".join(parts)
    return ""


async def stream_answer(
    context: str,
    question: str,
    user_id: str,
    history: Sequence[tuple[str, str]] = (),
) -> AsyncIterator[str]:
    chain = build_chain(user_id)
    chat_history = normalize_history(history)
    async for chunk in chain.astream(
        {"context": context, "question": question, "chat_history": chat_history}
    ):
        text = _chunk_text(chunk)
        if text:
            yield text
