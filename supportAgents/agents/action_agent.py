import json
import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from supportAgents.agents.prompts import ACTION_AGENT_SYSTEM_PROMPT, ACTION_SUMMARY_PROMPT
from supportAgents.graph.state import ActionPayload, SupportAgentState
from supportAgents.llm_clients import create_llm_client
from supportAgents.tools.pg_query import run_pg_query

MAX_ITERATIONS = 7


@tool
def pg_query(sql: str) -> str:
    """执行一条只读 SQL 查询，仅允许 SELECT / WITH / EXPLAIN / SHOW / DESCRIBE。

    返回 JSON 格式：{"columns": [...], "rows": [[...], ...], "row_count": N} 或 {"error": "..."}。
    可用此工具查看表结构（EXPLAIN、SHOW）、查询数据（SELECT）或了解 schema 信息。
    """
    result = run_pg_query(sql)
    return json.dumps(result, ensure_ascii=False, default=str)


AVAILABLE_TOOLS = [pg_query]


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
