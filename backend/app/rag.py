from collections.abc import AsyncIterator

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.llm_runtime import effective_api_key, get_llm_config
from app.retrieve import Hit

SYSTEM_PROMPT = """你是山东师范大学校园知识助手。只根据提供的 Context 回答。
Context 不足时明确说没有找到相关信息，不要编造。
中文提问用中文回答。可在答案中点出文件名。
Context 中同时出现[来源:公共]与[来源:用户]且内容不一致时，必须同时列出两边的说法，并明确指出存在冲突，不要只采用其中一方。"""


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
            ("user", "Context:\n{context}\n\nQuestion: {question}"),
        ]
    )
    llm = ChatOpenAI(
        model=cfg.model,
        api_key=effective_api_key(cfg),
        base_url=cfg.base_url,
        temperature=0.2,
        max_tokens=512,
        timeout=300,
        streaming=True,
    )
    return prompt | llm


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


async def stream_answer(context: str, question: str, user_id: str) -> AsyncIterator[str]:
    chain = build_chain(user_id)
    async for chunk in chain.astream({"context": context, "question": question}):
        text = _chunk_text(chunk)
        if text:
            yield text
