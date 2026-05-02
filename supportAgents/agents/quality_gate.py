from supportAgents.graph.state import SupportAgentState

# 分数阈值暂设为 0.0，仅空结果触发降级。
# RRF 融合分数量纲很小（rank=1 时约 0.016），在没有 rerank 归一化的情况下阈值难以校准。
# 后续 rerank 稳定开启后可以设阈值（如 0.05）启用 degraded_low_score。
_QUALITY_SCORE_THRESHOLD = 0.0


# 作用：检查检索结果质量，决定是否降级为直接回答。
# 零结果 → degraded_empty；否则 passed（分数阈值待 rerank 稳定后启用）。
def run_quality_gate(state: SupportAgentState) -> SupportAgentState:
    next_state: SupportAgentState = dict(state)

    retrieval = state.get("retrieval") or {}
    items = retrieval.get("items", [])

    if not items:
        next_state["quality"] = "degraded_empty"
        return next_state

    top_score = max(item.get("score", 0.0) for item in items)
    if top_score < _QUALITY_SCORE_THRESHOLD:
        next_state["quality"] = "degraded_low_score"
        return next_state

    next_state["quality"] = "passed"
    return next_state
