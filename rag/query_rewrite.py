import json
import os
import re
from dataclasses import dataclass

from langchain_classic.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from rag.config import settings
from rag.text_search import extract_query_keywords, normalize_search_text


_FILLER_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r"[，,。！？!?\s]*(这块|这边|这一块|这个问题|这个情况|这种情况)[，,。！？!?\s]*",
        r"[，,。！？!?\s]*(帮我看下|帮忙看下|先看下|看一下|瞅一下|瞄一下)[，,。！？!?\s]*",
        r"[，,。！？!?\s]*(老是|一直|总是|有点|感觉|像是|更像是)[，,。！？!?\s]*",
        r"[，,。！？!?\s]*(我现在|目前|现在|这会儿)[，,。！？!?\s]*",
    ]
]
_TYPO_REPLACEMENTS = {
    "知试": "知识",
    "混检": "混合检索",
    "重排": "rerank",
    "精排": "rerank",
    "召回率": "召回",
    "向量库": "向量检索",
}
_ALIAS_REPLACEMENTS = {
    "飞书库": "飞书知识库",
    "知识库接入这块": "知识库接入",
    "知识同步链路": "知识同步链路",
    "知识同步": "知识同步链路",
    "答案可信度": "回答可信度",
    "答案相关性": "回答相关性",
    "上下文覆盖": "上下文覆盖率",
}
_COLLOQUIAL_MARKERS = {
    "这块",
    "这边",
    "那个",
    "咋",
    "啥",
    "老出问题",
    "不太对",
    "更像是",
}
_MAX_VARIANTS = 4
_SUPPORTED_REWRITE_MODES = {"fast", "balanced", "deep"}


@dataclass(frozen=True)
class RewriteQueryVariant:
    # 作用：描述一条参与多路召回的查询变体及其融合权重。
    text: str
    weight: float
    reason: str


@dataclass(frozen=True)
class QueryRewriteResult:
    # 作用：统一承载 rewrite 结果，方便检索链路做多路召回和调试。
    original_query: str
    normalized_query: str
    variants: list[RewriteQueryVariant]
    used_llm: bool


# 作用：用规则替换常见错别字和领域别名，先把明显脏输入拉回知识库术语。
def _replace_known_terms(text: str) -> str:
    normalized = text
    for source, target in {**_TYPO_REPLACEMENTS, **_ALIAS_REPLACEMENTS}.items():
        normalized = normalized.replace(source, target)
    return normalized


# 作用：去掉对检索无帮助的口语填充，尽量保留用户原意里的产品词和症状词。
def _strip_fillers(text: str) -> str:
    normalized = text
    for pattern in _FILLER_PATTERNS:
        normalized = pattern.sub(" ", normalized)
    return normalize_search_text(normalized)


# 作用：把用户原问题清洗成更适合检索的标准化查询。
def normalize_query_for_retrieval(query: str) -> str:
    normalized = normalize_search_text(query)
    normalized = _replace_known_terms(normalized)
    normalized = _strip_fillers(normalized)
    return normalize_search_text(normalized)


# 作用：基于规则提炼一条更偏关键词风格的查询，补足口语问题的检索信号。
def _build_keyword_query(query: str) -> str:
    keywords = extract_query_keywords(query, limit=8)
    return " ".join(keywords)


# 作用：只在问题明显口语化、歧义重或规则清洗后变化较大时，才触发 LLM 改写。
def _should_use_llm(query: str, normalized_query: str) -> bool:
    if not settings.rag.enable_llm_query_rewrite:
        return False
    if not os.getenv("DEEPSEEK_API_KEY"):
        return False
    if normalized_query != query:
        return True
    lowered_query = query.lower()
    if any(marker in lowered_query for marker in _COLLOQUIAL_MARKERS):
        return True
    return len(extract_query_keywords(query, limit=4)) <= 2


# 作用：把模型输出解析成结构化查询列表，解析失败时直接降级为空列表。
def _parse_llm_queries(content: str) -> list[str]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            return []
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

    if not isinstance(payload, dict):
        return []
    search_queries = payload.get("search_queries")
    if not isinstance(search_queries, list):
        return []

    queries: list[str] = []
    for item in search_queries:
        if not isinstance(item, str):
            continue
        normalized_item = normalize_query_for_retrieval(item)
        if normalized_item:
            queries.append(normalized_item)
    return queries


# 作用：让模型只产出适合检索的 search query，不回答问题也不凭空补事实。
def _rewrite_with_llm(query: str, normalized_query: str, max_queries: int) -> list[str]:
    model = init_chat_model(settings.rag.query_rewrite_model)
    response = model.invoke(
        [
            SystemMessage(
                content=(
                    "你是知识库检索改写助手。"
                    "你的任务是把用户问题改写成更适合知识库检索的查询。"
                    "不要回答问题，不要新增原问题里没有依据的事实。"
                    "优先保留正式产品名、功能名、错误现象和关键约束。"
                    "只输出 JSON。"
                )
            ),
            HumanMessage(
                content=(
                    f"用户原问题：{query}\n"
                    f"规则清洗后：{normalized_query}\n"
                    f"最多输出 {max_queries} 条 search query。\n"
                    '输出格式：{"search_queries":["...", "..."]}'
                )
            ),
        ]
    )
    return _parse_llm_queries(getattr(response, "content", ""))


# 作用：构建最终参与召回的查询变体，默认保留原问题并追加更稳的补充查询。
def build_query_rewrite_result(
    query: str,
    *,
    use_query_rewrite: bool | None = None,
) -> QueryRewriteResult:
    original_query = normalize_search_text(query)
    normalized_query = normalize_query_for_retrieval(original_query)
    should_use_rewrite = (
        settings.rag.enable_query_rewrite if use_query_rewrite is None else use_query_rewrite
    )
    rewrite_mode = settings.rag.query_rewrite_mode.lower().strip()
    if rewrite_mode not in _SUPPORTED_REWRITE_MODES:
        rewrite_mode = "fast"

    variants: list[RewriteQueryVariant] = [RewriteQueryVariant(text=original_query, weight=1.0, reason="original")]
    used_llm = False
    if not should_use_rewrite:
        return QueryRewriteResult(
            original_query=original_query,
            normalized_query=normalized_query,
            variants=variants,
            used_llm=False,
        )

    if normalized_query and normalized_query != original_query:
        variants.append(
            RewriteQueryVariant(
                text=normalized_query,
                weight=settings.rag.query_rewrite_normalized_weight,
                reason="normalized",
            )
        )

    if rewrite_mode in {"balanced", "deep"}:
        keyword_query = _build_keyword_query(normalized_query or original_query)
        if keyword_query and keyword_query not in {variant.text for variant in variants}:
            variants.append(RewriteQueryVariant(text=keyword_query, weight=0.8, reason="keywords"))

    if rewrite_mode == "deep" and _should_use_llm(original_query, normalized_query):
        try:
            llm_queries = _rewrite_with_llm(
                original_query,
                normalized_query,
                max_queries=settings.rag.query_rewrite_max_queries,
            )
        except Exception:
            llm_queries = []
        else:
            used_llm = bool(llm_queries)

        for llm_query in llm_queries:
            if llm_query in {variant.text for variant in variants}:
                continue
            variants.append(RewriteQueryVariant(text=llm_query, weight=0.7, reason="llm"))
            if len(variants) >= _MAX_VARIANTS:
                break

    return QueryRewriteResult(
        original_query=original_query,
        normalized_query=normalized_query,
        variants=variants[:_MAX_VARIANTS],
        used_llm=used_llm,
    )
