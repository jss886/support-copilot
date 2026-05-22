from langgraph.graph import END, START, StateGraph

from supportAgents.agents import (
    run_action_agent,
    run_answer_agent,
    run_orchestrator,
    run_quality_gate,
    run_retrieval_agent,
)
from supportAgents.agents.plan_reflection_agent import run_plan_reflection
from supportAgents.agents.planner_agent import run_execute_subtasks, run_planner
from supportAgents.agents.synthesizer_agent import run_synthesizer
from supportAgents.graph.state import SupportAgentState


# 作用：根据 orchestrator 写入的 intent 决定后续走检索、工具还是直接回答链路。
def _route_after_orchestrator(state: SupportAgentState) -> str:
    complexity = state.get("complexity", "simple")
    if complexity == "complex":
        return "planner"

    intent = state.get("intent", "fallback")
    if intent == "tool_only":
        return "action"
    if intent == "knowledge_qa":
        return "retrieval"
    return "answer"


# 作用：在复杂任务执行后根据 reflection 结果决定是结束、重试还是补规划。
def _route_after_reflection(state: SupportAgentState) -> str:
    reflection = state.get("reflection") or {}
    action = reflection.get("next_action", "finish")
    if action == "retry":
        return "retry"
    if action == "replan":
        return "replan"
    return "finish"


def build_support_graph():
    builder = StateGraph(SupportAgentState)
    builder.add_node("orchestrator", run_orchestrator)
    builder.add_node("retrieval", run_retrieval_agent)
    builder.add_node("quality_gate", run_quality_gate)
    builder.add_node("action", run_action_agent)
    builder.add_node("answer", run_answer_agent)
    builder.add_node("planner", run_planner)
    builder.add_node("execute_subtasks", run_execute_subtasks)
    builder.add_node("plan_reflection", run_plan_reflection)
    builder.add_node("synthesizer", run_synthesizer)

    builder.add_edge(START, "orchestrator")
    builder.add_conditional_edges(
        "orchestrator",
        _route_after_orchestrator,
        {
            "planner": "planner",
            "retrieval": "retrieval",
            "action": "action",
            "answer": "answer",
        },
    )
    # 作用：检索结果先过质量门，再进入回答节点。
    builder.add_edge("retrieval", "quality_gate")
    builder.add_edge("quality_gate", "answer")
    # 作用：工具执行完成后统一走回答节点。
    builder.add_edge("action", "answer")
    # 作用：复杂任务先规划、再执行，再由 reflection 决定是否继续迭代。
    builder.add_edge("planner", "execute_subtasks")
    builder.add_edge("execute_subtasks", "plan_reflection")
    builder.add_conditional_edges(
        "plan_reflection",
        _route_after_reflection,
        {
            "finish": "synthesizer",
            "retry": "execute_subtasks",
            "replan": "planner",
        },
    )
    builder.add_edge("answer", END)
    builder.add_edge("synthesizer", END)
    return builder.compile()


# 作用：提供统一入口，方便 CLI、API 或测试直接调用整条 graph。
def run_support_graph(state: SupportAgentState) -> SupportAgentState:
    graph = build_support_graph()
    return graph.invoke(state)
