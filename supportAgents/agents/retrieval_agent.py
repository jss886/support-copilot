from rag.models import ChunkRecord
from rag.query_rewrite import build_query_rewrite_result
from rag.retrieval import retrieve
from supportAgents.graph.state import RetrievalItem, SupportAgentState


# 作用：把检索结果拼成统一上下文文本，后续 answer_agent 可以直接复用。
def build_context_text(retrieved: list[tuple[float, ChunkRecord]]) -> str:
    blocks: list[str] = []
    for rank, (score, record) in enumerate(retrieved, start=1):
        blocks.append(
            f"[片段{rank}] score={score:.4f} source={record.source} "
            f"range=({record.start}, {record.end})\n{record.text}"
        )
    return "\n\n".join(blocks)


# 作用：把 ChunkRecord 转成可序列化结构，方便 API 和 graph state 直接传递。
def _to_retrieval_item(score: float, record: ChunkRecord) -> RetrievalItem:
    return RetrievalItem(
        score=score,
        source=record.source,
        start=record.start,
        end=record.end,
        text=record.text,
        metadata=record.metadata,
    )


# 作用：封装现有 RAG 检索链路，把 rewrite、证据列表和上下文文本统一写入 state。
def run_retrieval_agent(
    state: SupportAgentState,
    *,
    top_k: int | None = None,
    candidate_top_k: int | None = None,
    source: str | None = None,
    use_rerank: bool | None = None,
    use_query_rewrite: bool | None = None,
) -> SupportAgentState:
    query = state.get("user_query", "").strip()
    if not query:
        next_state: SupportAgentState = dict(state)
        next_state["error"] = "retrieval_agent_missing_query"
        return next_state

    rewrite_result = build_query_rewrite_result(
        query,
        messages=state.get("messages"),
        use_query_rewrite=use_query_rewrite,
    )
    retrieved = retrieve(
        query=query,
        messages=state.get("messages"),
        top_k=top_k,
        source=source,
        candidate_top_k=candidate_top_k,
        use_rerank=use_rerank,
        use_query_rewrite=use_query_rewrite,
    )

    next_state: SupportAgentState = dict(state)
    hyde_variant = next(
        (variant for variant in rewrite_result.variants if variant.variant_type == "hyde"),
        None,
    )
    next_state["retrieval"] = {
        "query": query,
        "rewritten_queries": [
            variant.text for variant in rewrite_result.variants if variant.variant_type == "query"
        ],
        "hyde_document": hyde_variant.text if hyde_variant else "",
        "items": [_to_retrieval_item(score, record) for score, record in retrieved],
        "context_text": build_context_text(retrieved),
    }
    return next_state
