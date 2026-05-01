from .state import SupportAgentState, create_initial_state


# 作用：延迟导入 graph builder，避免 agents 和 graph 在包初始化阶段互相引用。
def build_support_graph():
    from .builder import build_support_graph as _build_support_graph

    return _build_support_graph()


# 作用：提供懒加载的 graph 运行入口，减少包级导入时的循环依赖。
def run_support_graph(state: SupportAgentState) -> SupportAgentState:
    from .builder import run_support_graph as _run_support_graph

    return _run_support_graph(state)


__all__ = [
    "SupportAgentState",
    "build_support_graph",
    "create_initial_state",
    "run_support_graph",
]
