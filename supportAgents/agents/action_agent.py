import json
import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from supportAgents.agents.prompts import ACTION_AGENT_SYSTEM_PROMPT, ACTION_SUMMARY_PROMPT
from supportAgents.graph.state import ActionPayload, SupportAgentState
from supportAgents.llm_clients import create_llm_client
from supportAgents.tools.pg_query import run_pg_query
from supportAgents.tools.tavily_search import run_tavily_search, run_tavily_search_context

MAX_ITERATIONS = 7


@tool
def pg_query(sql: str) -> str:
    """执行一条只读 SQL 查询，仅允许 SELECT / WITH / EXPLAIN / SHOW / DESCRIBE。

    返回 JSON 格式：{"columns": [...], "rows": [[...], ...], "row_count": N} 或 {"error": "..."}。
    可用此工具查看表结构（EXPLAIN、SHOW）、查询数据（SELECT）或了解 schema 信息。
    """
    result = run_pg_query(sql)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def tavily_search(
    query: str,
    search_depth: str = "basic",
    topic: str = "general",
    days: int = 7,
    max_results: int = 5,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    include_answer: bool = False,
    include_raw_content: bool = False,
) -> str:
    """执行网络搜索，从互联网获取最新信息。

    参数：
    - query: 搜索关键词或问题
    - search_depth: "basic"(快速) 或 "advanced"(深度)
    - topic: "general"(通用) / "news"(新闻) / "finance"(财经)
    - days: 搜索最近多少天的内容，默认7天
    - max_results: 最大返回结果数，默认5
    - include_domains: 限定搜索域名列表
    - exclude_domains: 排除域名列表
    - include_answer: 是否包含 AI 生成的回答摘要
    - include_raw_content: 是否包含网页原始内容

    返回 JSON 格式搜索结果，包含标题、URL、摘要等信息。
    """
    result = run_tavily_search(
        query=query,
        search_depth=search_depth,
        topic=topic,
        days=days,
        max_results=max_results,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        include_answer=include_answer,
        include_raw_content=include_raw_content,
    )
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def tavily_search_context(
    query: str,
    search_depth: str = "basic",
    topic: str = "general",
    days: int = 7,
    max_results: int = 5,
    max_tokens: int = 4000,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> str:
    """获取搜索上下文字符串（自动截断到 max_tokens），适合直接注入 LLM 上下文。

    参数：
    - query: 搜索关键词或问题
    - search_depth: "basic"(快速) 或 "advanced"(深度)
    - topic: "general"(通用) / "news"(新闻) / "finance"(财经)
    - days: 搜索最近多少天的内容，默认7天
    - max_results: 最大返回结果数，默认5
    - max_tokens: 返回内容的最大 token 数，默认4000
    - include_domains: 限定搜索域名列表
    - exclude_domains: 排除域名列表

    返回包含搜索上下文字符串的 JSON。
    """
    result = run_tavily_search_context(
        query=query,
        search_depth=search_depth,
        topic=topic,
        days=days,
        max_results=max_results,
        max_tokens=max_tokens,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
    )
    return json.dumps(result, ensure_ascii=False, default=str)


AVAILABLE_TOOLS = [pg_query, tavily_search, tavily_search_context]


def _build_action_llm():
    model = os.environ.get("ACTION_AGENT_MODEL", "deepseek-v4-flash")
    base_url = os.environ.get("ACTION_AGENT_BASE_URL")
    client = create_llm_client(
        "deepseek",
        model,
        base_url=base_url,
        timeout=60,
        max_retries=2,
    )
    return client.get_llm()


# 作用：执行工具调用循环，LLM 自主决定何时停止或继续调用工具，
# 达到最大轮次或 LLM 判断无需更多工具时退出，将所有调用记录存入 state。
def run_action_agent(state: SupportAgentState) -> SupportAgentState:
    next_state: SupportAgentState = dict(state)
    if next_state.get("error"):
        return next_state

    query = next_state.get("user_query", "")
    route_reason = next_state.get("route_reason", "")

    llm = _build_action_llm()
    llm_with_tools = llm.bind_tools(AVAILABLE_TOOLS)

    messages = [
        SystemMessage(content=ACTION_AGENT_SYSTEM_PROMPT),
        HumanMessage(
            content=f"用户问题：{query}\n路由原因：{route_reason}\n请通过工具调用收集相关信息。"
        ),
    ]

    action_history: list[ActionPayload] = []

    for _iteration in range(MAX_ITERATIONS):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not isinstance(response, AIMessage) or not response.tool_calls:
            # LLM 判断信息已足够，不再调用工具。取其 content 作为总结。
            summary_text = getattr(response, "content", "") or ""
            # 如果 LLM 没写总结（content 为空），补一句提示
            if not summary_text.strip():
                summary_text = "工具调用已完成，详见调用记录。"
            next_state["action_history"] = action_history
            next_state["action_summary"] = summary_text
            return next_state

        for tc in response.tool_calls:
            tool_name = tc.get("name", "")
            tool_args = tc.get("args", {})
            tool_id = tc.get("id", "")

            if tool_name == "pg_query":
                sql = tool_args.get("sql", "")
                raw = run_pg_query(sql)
                if raw.get("error"):
                    result_text = f"查询失败: {raw['error']}"
                    action_history.append(
                        ActionPayload(
                            tool_name=tool_name,
                            tool_input={"sql": sql},
                            tool_output=raw.get("error", ""),
                            status="error",
                            error_message=raw["error"],
                        )
                    )
                else:
                    result_text = json.dumps(raw, ensure_ascii=False, default=str)
                    action_history.append(
                        ActionPayload(
                            tool_name=tool_name,
                            tool_input={"sql": sql},
                            tool_output=raw,
                            status="success",
                        )
                    )
            elif tool_name == "tavily_search":
                raw = run_tavily_search(
                    query=tool_args.get("query", ""),
                    search_depth=tool_args.get("search_depth", "basic"),
                    topic=tool_args.get("topic", "general"),
                    days=tool_args.get("days", 7),
                    max_results=tool_args.get("max_results", 5),
                    include_domains=tool_args.get("include_domains"),
                    exclude_domains=tool_args.get("exclude_domains"),
                    include_answer=tool_args.get("include_answer", False),
                    include_raw_content=tool_args.get("include_raw_content", False),
                )
                if raw.get("error"):
                    result_text = f"搜索失败: {raw['error']}"
                    action_history.append(
                        ActionPayload(
                            tool_name=tool_name,
                            tool_input=tool_args,
                            tool_output=raw.get("error", ""),
                            status="error",
                            error_message=raw["error"],
                        )
                    )
                else:
                    result_text = json.dumps(raw, ensure_ascii=False, default=str)
                    action_history.append(
                        ActionPayload(
                            tool_name=tool_name,
                            tool_input=tool_args,
                            tool_output=raw,
                            status="success",
                        )
                    )
            elif tool_name == "tavily_search_context":
                raw = run_tavily_search_context(
                    query=tool_args.get("query", ""),
                    search_depth=tool_args.get("search_depth", "basic"),
                    topic=tool_args.get("topic", "general"),
                    days=tool_args.get("days", 7),
                    max_results=tool_args.get("max_results", 5),
                    max_tokens=tool_args.get("max_tokens", 4000),
                    include_domains=tool_args.get("include_domains"),
                    exclude_domains=tool_args.get("exclude_domains"),
                )
                if raw.get("error"):
                    result_text = f"搜索失败: {raw['error']}"
                    action_history.append(
                        ActionPayload(
                            tool_name=tool_name,
                            tool_input=tool_args,
                            tool_output=raw.get("error", ""),
                            status="error",
                            error_message=raw["error"],
                        )
                    )
                else:
                    result_text = json.dumps(raw, ensure_ascii=False, default=str)
                    action_history.append(
                        ActionPayload(
                            tool_name=tool_name,
                            tool_input=tool_args,
                            tool_output=raw,
                            status="success",
                        )
                    )
            else:
                result_text = f"未知工具: {tool_name}"
                action_history.append(
                    ActionPayload(
                        tool_name=tool_name,
                        tool_input=tool_args,
                        status="error",
                        error_message=result_text,
                    )
                )

            messages.append(ToolMessage(content=result_text, tool_call_id=tool_id))

    # 达到最大迭代次数，让 LLM 基于已有信息生成总结。
    messages.append(HumanMessage(content=ACTION_SUMMARY_PROMPT))
    final_response = llm.invoke(messages)
    summary_text = getattr(final_response, "content", "") or ""

    next_state["action_history"] = action_history
    next_state["action_summary"] = summary_text
    return next_state
