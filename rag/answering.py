from langchain_classic.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from rag.retrieval import retrieve


def answer_question(
    question: str,
    top_k: int = 3,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
    source: str | None = None,
    embedding_dimensions: int | None = None,
) -> str:
    retrieved = retrieve(
        query=question,
        top_k=top_k,
        jdbc_url=jdbc_url,
        db_user=db_user,
        db_password=db_password,
        source=source,
        embedding_dimensions=embedding_dimensions,
    )
    context_blocks = []
    for rank, (score, record) in enumerate(retrieved, start=1):
        context_blocks.append(
            f"[片段{rank}] score={score:.4f} source={record.source} "
            f"range=({record.start}, {record.end})\n{record.text}"
        )

    context = "\n\n".join(context_blocks)
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
