import json
import os
import re
from dataclasses import dataclass
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage

from supportAgents.agents.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from supportAgents.graph.state import ComplexityType, IntentType, SupportAgentState
from supportAgents.llm_clients import create_llm_client

RouteCategory = Literal["doc_qa", "code_qa", "tool_only", "direct_answer", "fallback"]

_VALID_INTENTS = {"doc_qa", "code_qa", "tool_only", "direct_answer", "fallback"}

_CODE_KEYWORDS = {
    "代码", "code", "bug", "报错", "异常", "接口", "函数", "类", "traceback", "sql",
}
_TOOL_KEYWORDS = {
    "调用", "执行", "运行", "检查", "查询", "tool", "curl", "脚本", "命令",
}
_DIRECT_ANSWER_KEYWORDS = {
    "你好", "hi", "hello", "谢谢", "是什么", "什么意思",
}


@dataclass(frozen=True)
class IntentDecision:
    intent: IntentType
    reason: str
    complexity: ComplexityType = "simple"


# 作用：构造 orchestrator 专用模型实例，用 DeepSeek V4 Flash 保证低延迟和低成本。
def _build_orchestrator_llm():
    model = os.environ.get("SUPPORT_ORCHESTRATOR_MODEL", "deepseek-v4-flash")
    client = create_llm_client("deepseek", model, timeout=15, max_retries=1, temperature=0)
    return client.get_llm()


# 作用：把 LLM 输出的 JSON 解析为结构化的路由决策，解析失败时返回 None。
def _parse_intent_json(content: str) -> IntentDecision | None:
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

    intent = payload.get("intent", "").strip().lower()
    reason = payload.get("reason", "").strip()
    if intent not in _VALID_INTENTS:
        return None
    complexity_raw = payload.get("complexity", "simple").strip().lower()
    complexity: ComplexityType = "complex" if complexity_raw == "complex" else "simple"
    return IntentDecision(intent=intent, reason=reason or "llm_routed", complexity=complexity)


# 作用：用 LLM 判断用户意图，返回结构化路由决策。
def _decide_intent_with_llm(query: str) -> IntentDecision | None:
    llm = _build_orchestrator_llm()
    response = llm.invoke(
        [
            SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT),
            HumanMessage(content=f"用户问题：{query}"),
        ]
    )
    return _parse_intent_json(getattr(response, "content", "") or "")


# 作用：把用户问题归一成便于规则判断的文本。
def _normalize_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


# 作用：关键词规则路由，作为 LLM 路由失败时的兜底方案。
def decide_intent(query: str) -> IntentDecision:
    normalized_query = _normalize_query(query)
    if not normalized_query:
        return IntentDecision(intent="fallback", reason="empty_query")

    if any(keyword in normalized_query for keyword in _TOOL_KEYWORDS):
        return IntentDecision(intent="tool_only", reason="matched_tool_keyword")

    if any(keyword in normalized_query for keyword in _CODE_KEYWORDS):
        return IntentDecision(intent="code_qa", reason="matched_code_keyword")

    if any(keyword in normalized_query for keyword in _DIRECT_ANSWER_KEYWORDS) and len(
        normalized_query
    ) <= 24:
        return IntentDecision(intent="direct_answer", reason="matched_direct_answer_keyword")

    if len(normalized_query) <= 6:
        return IntentDecision(intent="direct_answer", reason="short_query")

    return IntentDecision(intent="doc_qa", reason="default_to_retrieval")


# 作用：执行总控路由节点。
# auto 模式优先用 LLM 路由，失败时自动降级为关键词规则；
# direct/rag 模式直接跳过路由判断。
def run_orchestrator(state: SupportAgentState) -> SupportAgentState:
    query = state.get("user_query", "")
    mode = state.get("mode", "auto")

    next_state: SupportAgentState = dict(state)
    next_state["normalized_query"] = _normalize_query(query)

    if mode == "direct":
        next_state["intent"] = "direct_answer"
        next_state["route_reason"] = "user_selected_direct_mode"
        return next_state

    if mode == "rag":
        next_state["intent"] = "doc_qa"
        next_state["route_reason"] = "user_selected_rag_mode"
        return next_state

    # auto 模式：优先 LLM 路由，失败时降级为关键词规则。
    try:
        decision = _decide_intent_with_llm(query)
        if decision is not None:
            next_state["intent"] = decision.intent
            next_state["route_reason"] = f"llm: {decision.reason}"
            next_state["complexity"] = decision.complexity
            return next_state
    except Exception:
        pass

    decision = decide_intent(query)
    next_state["intent"] = decision.intent
    next_state["route_reason"] = f"keyword_fallback: {decision.reason}"
    next_state["complexity"] = decision.complexity
    return next_state
