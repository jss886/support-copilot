import os
import re
from functools import lru_cache

from langchain_classic.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from rag.config import settings

_WHITESPACE_RE = re.compile(r"\s+")


# 作用：统一清理上下文文本里的空白，避免写入数据库时带入噪声换行。
def _normalize_context_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


# 作用：把整篇文档压缩成适合提供给上下文化模型的窗口，兼顾全局主题和局部片段附近内容。
def _build_document_window(document_text: str, start: int, end: int) -> str:
    max_chars = settings.rag.contextual_retrieval_max_document_chars
    normalized_document = document_text.strip()
    if len(normalized_document) <= max_chars:
        return normalized_document

    local_budget = max_chars // 2
    local_start = max(0, start - local_budget // 2)
    local_end = min(len(document_text), end + local_budget // 2)
    local_window = document_text[local_start:local_end].strip()

    head_budget = max(0, (max_chars - len(local_window)) // 2)
    head_window = document_text[:head_budget].strip()
    tail_window = document_text[-head_budget:].strip() if head_budget else ""
    combined_parts = [part for part in [head_window, local_window, tail_window] if part]
    return _normalize_context_text("\n".join(combined_parts))[:max_chars]


# 作用：判断当前环境是否适合启用 chunk 上下文化，避免模型未配置时阻塞入库。
def _can_use_contextual_retrieval() -> bool:
    if not settings.rag.enable_contextual_retrieval:
        return False
    return bool(os.getenv("DEEPSEEK_API_KEY"))


# 作用：懒加载上下文化使用的对话模型，避免普通入库路径无谓初始化。
@lru_cache(maxsize=1)
def _build_contextual_retrieval_model():
    return init_chat_model(settings.rag.contextual_retrieval_model)


# 作用：让模型基于整篇文档为当前 chunk 生成一段简短定位说明。
def generate_chunk_context(
    *,
    document_text: str,
    chunk_text: str,
    start: int,
    end: int,
    title_path: list[str] | None = None,
) -> str:
    if not _can_use_contextual_retrieval():
        return ""

    document_window = _build_document_window(document_text, start, end)
    if not document_window or not chunk_text.strip():
        return ""

    title_hint = " > ".join(title_path or [])
    title_line = f"标题路径：{title_hint}\n" if title_hint else ""
    model = _build_contextual_retrieval_model()
    response = model.invoke(
        [
            SystemMessage(
                content=(
                    "你是知识库切片上下文化助手。\n"
                    "请根据整篇文档上下文，为当前 chunk 生成一段简短说明，帮助后续检索更容易理解这个 chunk 的主题、对象、场景或指代关系。\n"
                    "要求：\n"
                    "1. 只输出上下文说明，不要重复 chunk 原文。\n"
                    "2. 控制在 1-2 句话内，尽量简洁。\n"
                    "3. 不要编造文档中没有的信息。\n"
                    "4. 优先补足主语、模块、时间、场景、错误对象等缺失上下文。"
                )
            ),
            HumanMessage(
                content=(
                    f"{title_line}"
                    f"<document>\n{document_window}\n</document>\n\n"
                    f"<chunk>\n{chunk_text}\n</chunk>\n\n"
                    "请输出适合拼接在 chunk 前面的简短上下文说明。"
                )
            ),
        ]
    )
    context_text = _normalize_context_text(getattr(response, "content", "") or "")
    return context_text[: settings.rag.contextual_retrieval_max_context_chars]


# 作用：把上下文化说明前缀拼接到 chunk 前，供 embedding 和全文索引复用。
def contextualize_chunk_text(
    *,
    document_text: str,
    chunk_text: str,
    start: int,
    end: int,
    title_path: list[str] | None = None,
) -> str:
    context_text = generate_chunk_context(
        document_text=document_text,
        chunk_text=chunk_text,
        start=start,
        end=end,
        title_path=title_path,
    )
    if not context_text:
        return chunk_text
    return f"【上下文】{context_text}\n{chunk_text}"
