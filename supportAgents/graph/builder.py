from langgraph.graph import END, START, StateGraph

from supportAgents.agents import (
    run_answer_agent,
    run_orchestrator,
    run_quality_gate,
    run_retrieval_agent,
)
from supportAgents.graph.state import SupportAgentState


# 作用：根据 orchestrator 写入的 intent 决定后续走检索链路还是直接回答链路。
def _route_after_orchestrator(state: SupportAgentState) -> str:
    intent = state.get("intent", "fallback")
    if intent in {"doc_qa", "code_qa"}:
        return "retrieval"
    return "answer"


def build_support_graph():
    builder = StateGraph(SupportAgentState)
    builder.add_node("orchestrator", run_orchestrator)
    builder.add_node("retrieval", run_retrieval_agent)
    builder.add_node("quality_gate", run_quality_gate)
    builder.add_node("answer", run_answer_agent)

    builder.add_edge(START, "orchestrator")
    builder.add_conditional_edges(
        "orchestrator",
        _route_after_orchestrator,
        {
            "retrieval": "retrieval",
            "answer": "answer",
        },
    )
    # retrieval → quality_gate → answer：检索结果先过质量检查，再统一进入回答节点。
    builder.add_edge("retrieval", "quality_gate")
    builder.add_edge("quality_gate", "answer")
    builder.add_edge("answer", END)
    return builder.compile()


# 作用：提供统一入口，方便 CLI、API 或后续测试直接调用整条 graph。
def run_support_graph(state: SupportAgentState) -> SupportAgentState:
    graph = build_support_graph()
    return graph.invoke(state)
