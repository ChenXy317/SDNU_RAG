from collections.abc import AsyncIterator, Sequence

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from app.llm_runtime import effective_api_key, get_llm_config
from app.retrieve import Hit

SYSTEM_PROMPT = """你是山东师范大学校园知识助手。

事实只来自本次用户消息中的 Context：
- Context 没写的就当不知道。即使你记得，也明确说没有找到相关信息，不要用记忆补全，不要编造。
- 对话历史只用来理解指代和追问，例如「那」「刚才说的校区」。历史里出现过的说法不能当作本次事实。
- Context 是按相关度拼在一起的摘录，不是按顺序排好的文章。片段可能重叠，也可能和问题无关。忽略无关片段。不要把不同校区、不同事项拼成一件事。

回答：
- 中文提问用中文回答。
- 陈述事实时标出对应文件名。
- 上下文只能支持一部分时，只回答这一部分，并说明其余没有找到。
- 没有相关片段，或片段只是话题接近、里面没有答案时，直接说没有找到相关信息。

冲突：
- 两个片段对同一事实说法不一致时，不论同为公共、同为用户，还是公共与用户相对，都要同时列出两边的说法，标明来源和文件名，并写明存在冲突。不要只采用其中一方。
- 片段只是话题不同、彼此并不矛盾时，不要当成冲突。"""

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
