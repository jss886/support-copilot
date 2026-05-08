from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from supportAgents.agents.answer_agent import run_answer_agent
from supportAgents.agents.quality_gate import run_quality_gate
from supportAgents.agents.retrieval_agent import run_retrieval_agent
from supportAgents.graph.state import SupportAgentState


# 作用：构建 knowledge_qa worker 的局部子图，后续可以独立扩展重试、回退或额外节点。
@lru_cache(maxsize=1)
def build_retrieval_worker_graph():
    builder = StateGraph(SupportAgentState)
    builder.add_node("retrieval", run_retrieval_agent)
    builder.add_node("quality_gate", run_quality_gate)
    builder.add_node("answer", run_answer_agent)

    builder.add_edge(START, "retrieval")
    builder.add_edge("retrieval", "quality_gate")
    builder.add_edge("quality_gate", "answer")
    builder.add_edge("answer", END)
    return builder.compile()


# 作用：执行 retrieval worker 子图，保持 worker 调用层只依赖统一入口。
def run_retrieval_worker_graph(state: SupportAgentState) -> SupportAgentState:
    graph = build_retrieval_worker_graph()
    return graph.invoke(state)

