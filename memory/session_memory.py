import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage

from memory.db import load_session_state, save_session_state
from memory.models import SessionMemoryState, SessionSummaryPayload
from memory.prompts import SESSION_SUMMARY_SYSTEM_PROMPT
from supportAgents.graph.state import SupportAgentState
from supportAgents.llm_clients import create_llm_client

_SESSION_MEMORY_MAX_MESSAGES = 20


# 作用：构造会话记忆压缩使用的模型实例，专门负责把旧摘要和溢出消息压成结构化 summary。
def _build_memory_llm():
    model = os.environ.get("SUPPORT_MEMORY_MODEL", "deepseek-v4-flash")
    client = create_llm_client("deepseek", model, timeout=30, max_retries=1, temperature=0)
    return client.get_llm()


# 作用：把历史消息转成紧凑文本，便于 summary 模型理解上下文。
def _format_messages(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = message.get("role", "user")
        content = (message.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


# 作用：将 summary 结构转成稳定文本，便于 planner 和 synthesizer 复用。
def _format_summary(summary: SessionSummaryPayload) -> str:
    if not summary:
        return "无历史 SessionSummary。"
    return (
        f"summary: {summary.get('summary', '')}\n"
        f"current_goal: {summary.get('current_goal', '')}\n"
        f"key_facts: {summary.get('key_facts', [])}\n"
        f"open_issues: {summary.get('open_issues', [])}\n"
        f"failed_attempts: {summary.get('failed_attempts', [])}"
    )


# 作用：解析 SessionSummary JSON，保证短期记忆结构稳定。
def _parse_summary_json(content: str) -> SessionSummaryPayload | None:
    if not content:
        return None
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return SessionSummaryPayload(
        summary=str(payload.get("summary", "")).strip(),
        key_facts=[str(item).strip() for item in payload.get("key_facts", []) if str(item).strip()]
        if isinstance(payload.get("key_facts", []), list)
        else [],
        open_issues=[str(item).strip() for item in payload.get("open_issues", []) if str(item).strip()]
        if isinstance(payload.get("open_issues", []), list)
        else [],
        failed_attempts=[str(item).strip() for item in payload.get("failed_attempts", []) if str(item).strip()]
        if isinstance(payload.get("failed_attempts", []), list)
        else [],
        current_goal=str(payload.get("current_goal", "")).strip(),
    )


# 作用：在 LLM 不可用时生成最小 summary，至少保留目标和最近问题。
def _build_fallback_summary(messages: list[dict[str, str]]) -> SessionSummaryPayload:
    recent_contents = [
        (message.get("content") or "").strip()
        for message in messages
        if (message.get("content") or "").strip()
    ]
    latest_goal = recent_contents[-1] if recent_contents else ""
    return SessionSummaryPayload(
        summary="会话历史已压缩，当前保留最近一段排查上下文。",
        key_facts=[],
        open_issues=[latest_goal] if latest_goal else [],
        failed_attempts=[],
        current_goal=latest_goal,
    )


# 作用：把旧 summary 和溢出历史消息压缩成新的 SessionSummary。
def _summarize_messages(
    previous_summary: SessionSummaryPayload,
    messages_to_compress: list[dict[str, str]],
) -> SessionSummaryPayload:
    if not messages_to_compress:
        return previous_summary
    try:
        llm = _build_memory_llm()
        response = llm.invoke(
            [
                SystemMessage(content=SESSION_SUMMARY_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"旧的 SessionSummary：\n{_format_summary(previous_summary)}\n\n"
                        f"需要折叠进历史的消息：\n{_format_messages(messages_to_compress)}"
                    )
                ),
            ]
        )
        parsed = _parse_summary_json(getattr(response, "content", "") or "")
        if parsed is not None:
            return parsed
    except Exception:
        pass
    return _build_fallback_summary(messages_to_compress)


# 作用：根据 session 持久化状态和本轮消息构造可直接注入 prompt 的短期记忆。
def build_session_memory(state: SupportAgentState) -> SupportAgentState:
    next_state: SupportAgentState = dict(state)
    session_id = next_state.get("session_id", "")
    persisted_state = load_session_state(session_id) if session_id else {}
    memory_state = SessionMemoryState(persisted_state.get("session_memory", {}))
    previous_summary = SessionSummaryPayload(memory_state.get("summary", {}))
    compressed_message_count = int(memory_state.get("compressed_message_count", 0))

    messages = list(next_state.get("messages", []))
    overflow_messages = messages[:-_SESSION_MEMORY_MAX_MESSAGES] if len(messages) > _SESSION_MEMORY_MAX_MESSAGES else []
    recent_messages = messages[-_SESSION_MEMORY_MAX_MESSAGES:] if len(messages) > _SESSION_MEMORY_MAX_MESSAGES else messages

    if len(overflow_messages) > compressed_message_count:
        new_messages_to_compress = overflow_messages[compressed_message_count:]
        previous_summary = _summarize_messages(previous_summary, new_messages_to_compress)
        compressed_message_count = len(overflow_messages)

    next_state["memory"] = {
        "session_summary": previous_summary.get("summary", ""),
        "saved": False,
    }
    next_state["session_memory"] = {
        "summary": previous_summary,
        "compressed_message_count": compressed_message_count,
    }
    next_state["recent_messages"] = recent_messages
    return next_state


# 作用：在本轮回答结束后把最新短期记忆落回 sessions.state。
def persist_session_memory(state: SupportAgentState) -> None:
    session_id = state.get("session_id", "")
    if not session_id:
        return
    summary_state = state.get("session_memory") or {}
    save_session_state(
        session_id=session_id,
        user_id=state.get("user_id", "anonymous"),
        state={"session_memory": summary_state},
        current_topic=(summary_state.get("summary") or {}).get("current_goal", ""),
        last_user_query=state.get("user_query", ""),
        last_answer_summary=state.get("answer", "")[:200],
    )
