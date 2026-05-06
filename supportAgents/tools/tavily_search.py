from typing import Any, Sequence

from tavily import TavilyClient

from rag.config import settings


def _get_client() -> TavilyClient:
    return TavilyClient(
        api_key=settings.tavily.api_key,
        api_base_url=settings.tavily.api_base_url,
    )


def run_tavily_search(
    query: str,
    search_depth: str = "basic",
    topic: str = "general",
    days: int = 7,
    max_results: int = 5,
    include_domains: Sequence[str] | None = None,
    exclude_domains: Sequence[str] | None = None,
    include_answer: bool = False,
    include_raw_content: bool = False,
) -> dict[str, Any]:
    """执行一次 Tavily 网络搜索，返回结构化结果。"""
    if not settings.tavily.api_key:
        return {"error": "Tavily API Key 未配置，请在 config_local.py 中设置 tavily.api_key。"}

    try:
        client = _get_client()
        result = client.search(
            query=query,
            search_depth=search_depth,
            topic=topic,
            days=days,
            max_results=max_results,
            include_domains=list(include_domains) if include_domains else None,
            exclude_domains=list(exclude_domains) if exclude_domains else None,
            include_answer=include_answer,
            include_raw_content=include_raw_content,
        )
        return result
    except Exception as exc:
        return {"error": f"Tavily 搜索失败: {exc}"}


def run_tavily_search_context(
    query: str,
    search_depth: str = "basic",
    topic: str = "general",
    days: int = 7,
    max_results: int = 5,
    max_tokens: int = 4000,
    include_domains: Sequence[str] | None = None,
    exclude_domains: Sequence[str] | None = None,
) -> dict[str, Any]:
    """获取搜索上下文（自动截断到 max_tokens）。"""
    if not settings.tavily.api_key:
        return {"error": "Tavily API Key 未配置，请在 config_local.py 中设置 tavily.api_key。"}

    try:
        client = _get_client()
        context = client.get_search_context(
            query=query,
            search_depth=search_depth,
            topic=topic,
            days=days,
            max_results=max_results,
            max_tokens=max_tokens,
            include_domains=list(include_domains) if include_domains else None,
            exclude_domains=list(exclude_domains) if exclude_domains else None,
        )
        return {"context": context}
    except Exception as exc:
        return {"error": f"Tavily 搜索上下文获取失败: {exc}"}
