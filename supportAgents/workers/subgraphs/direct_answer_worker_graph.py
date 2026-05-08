from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from supportAgents.agents.answer_agent import run_answer_agent
from supportAgents.graph.state import SupportAgentState


# 作用：构建 direct answer worker 的局部子图，保持所有 worker 都使用统一的子图执行模型。
@lru_cache(maxsize=1)
def build_direct_answer_worker_graph():
    builder = StateGraph(SupportAgentState)
    builder.add_node("answer", run_answer_agent)

    builder.add_edge(START, "answer")
    builder.add_edge("answer", END)
    return builder.compile()


# 作用：执行 direct answer worker 子图。
def run_direct_answer_worker_graph(state: SupportAgentState) -> SupportAgentState:
    graph = build_direct_answer_worker_graph()
    return graph.invoke(state)
