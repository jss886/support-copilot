from dataclasses import dataclass
from typing import Literal

from supportAgents.graph.state import IntentType, SupportAgentState


RouteCategory = Literal["doc_qa", "code_qa", "tool_only", "direct_answer", "fallback"]

_CODE_KEYWORDS = {
    "代码",
    "code",
    "bug",
    "报错",
    "异常",
    "接口",
    "函数",
    "类",
    "traceback",
    "sql",
}
_TOOL_KEYWORDS = {
    "调用",
    "执行",
    "运行",
    "检查",
    "查询",
    "tool",
    "curl",
    "脚本",
    "命令",
}
_DIRECT_ANSWER_KEYWORDS = {
    "你好",
    "hi",
    "hello",
    "谢谢",
    "是什么",
    "什么意思",
}


@dataclass(frozen=True)
class IntentDecision:
    # 作用：承载一次路由判断结果，方便 graph 节点只消费结构化输出。
    intent: IntentType
    reason: str


# 作用：把用户问题归一成便于规则判断的文本，先满足第一版轻量路由需求。
def _normalize_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


# 作用：用可解释的轻量规则做第一版路由，后续再替换成 LLM router 也不影响上层协议。
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


# 作用：执行总控路由节点，根据用户选择的 mode 决定是跳过关键词路由还是走自动判断。
def run_orchestrator(state: SupportAgentState) -> SupportAgentState:
    query = state.get("user_query", "")
    mode = state.get("mode", "auto")

    next_state: SupportAgentState = dict(state)
    next_state["normalized_query"] = _normalize_query(query)

    # direct 模式：跳过检索，直接回答，不再匹配关键词
    if mode == "direct":
        next_state["intent"] = "direct_answer"
        next_state["route_reason"] = "user_selected_direct_mode"
        return next_state

    # rag 模式：强制走检索，不再匹配关键词
    if mode == "rag":
        next_state["intent"] = "doc_qa"
        next_state["route_reason"] = "user_selected_rag_mode"
        return next_state

    # auto 模式：走原有关键词规则路由
    decision = decide_intent(query)
    next_state["intent"] = decision.intent
    next_state["route_reason"] = decision.reason
    return next_state
