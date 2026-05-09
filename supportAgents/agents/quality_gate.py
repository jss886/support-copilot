from supportAgents.graph.state import SupportAgentState

# 作用：检查检索结果质量，决定是否降级为直接回答。
# 零结果 → degraded_empty；原始召回非空但全部被低分过滤掉 → degraded_low_score；其余通过。
def run_quality_gate(state: SupportAgentState) -> SupportAgentState:
    next_state: SupportAgentState = dict(state)

    retrieval = state.get("retrieval") or {}
    items = retrieval.get("items", [])
    raw_item_count = int(retrieval.get("raw_item_count", 0))
    filtered_item_count = int(retrieval.get("filtered_item_count", len(items)))

    # 完全没召回到候选，说明检索侧没有任何可用证据。
    if raw_item_count <= 0:
        next_state["quality"] = "degraded_empty"
        return next_state

    # 原始召回存在，但通过 gate 后一条都没剩，说明相关性过低，不应继续喂给回答模型。
    if filtered_item_count <= 0 or not items:
        next_state["quality"] = "degraded_low_score"
        return next_state

    next_state["quality"] = "passed"
    return next_state
