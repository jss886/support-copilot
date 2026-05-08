from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from supportAgents.agents.action_agent import run_action_agent
from supportAgents.agents.answer_agent import run_answer_agent
from supportAgents.graph.state import SupportAgentState


# 作用：构建 tool worker 的局部子图，后续可以在这里追加审批、重试或工具回退节点。
@lru_cache(maxsize=1)
def build_tool_worker_graph():
    builder = StateGraph(SupportAgentState)
    builder.add_node("action", run_action_agent)
    builder.add_node("answer", run_answer_agent)

    builder.add_edge(START, "action")
    builder.add_edge("action", "answer")
    builder.add_edge("answer", END)
    return builder.compile()


# 作用：执行 tool worker 子图，保持 worker 层只依赖统一入口。
def run_tool_worker_graph(state: SupportAgentState) -> SupportAgentState:
    graph = build_tool_worker_graph()
    return graph.invoke(state)
