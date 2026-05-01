from langchain_classic.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from rag.models import ChunkRecord
from rag.retrieval import retrieve


# 作用：把检索结果拼成统一的上下文文本，避免不同调用方重复维护片段格式。
def _build_context_blocks(retrieved: list[tuple[float, ChunkRecord]]) -> str:
    context_blocks = []
    for rank, (score, record) in enumerate(retrieved, start=1):
        context_blocks.append(
            f"[片段{rank}] score={score:.4f} source={record.source} "
            f"range=({record.start}, {record.end})\n{record.text}"
        )
    return "\n\n".join(context_blocks)


# 作用：基于已检索到的证据生成答案，供评测等场景复用，避免同一问题重复检索。
def answer_question_from_context(
    *,
    question: str,
    retrieved: list[tuple[float, ChunkRecord]],
) -> str:
    context = _build_context_blocks(retrieved)
    model = init_chat_model("deepseek-chat")
    response = model.invoke(
        [
            SystemMessage(
                content=(
                    "你是一个简洁可靠的 RAG 助手。"
                    "请严格基于提供的检索片段回答问题。"
                    "如果上下文不足，请明确说明。"
                )
            ),
            HumanMessage(content=f"问题：{question}\n\n检索上下文：\n{context}"),
        ]
    )
    return response.content


# 作用：执行完整问答链路，先检索上下文，再基于证据生成最终答案。
def answer_question(
    question: str,
    top_k: int = 5,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
    source: str | None = None,
    embedding_dimensions: int | None = None,
    candidate_top_k: int | None = None,
    use_rerank: bool | None = None,
    use_query_rewrite: bool | None = None,
) -> str:
    retrieved = retrieve(
        query=question,
        top_k=top_k,
        jdbc_url=jdbc_url,
        db_user=db_user,
        db_password=db_password,
        source=source,
        embedding_dimensions=embedding_dimensions,
        candidate_top_k=candidate_top_k,
        use_rerank=use_rerank,
        use_query_rewrite=use_query_rewrite,
    )
    return answer_question_from_context(question=question, retrieved=retrieved)
