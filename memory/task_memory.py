import json

from memory.db import _build_db_params
from rag.db import connect_postgres
from rag.embeddings import DashScopeEmbeddingClient

_TASK_MEMORY_SCORE_GATE = 0.55


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


# 作用：在 planner 前检索可复用 task_memory，只返回少量高相关经验。
def retrieve_task_memories(query: str, *, top_k: int = 3) -> str:
    if not query.strip():
        return ""
    client = DashScopeEmbeddingClient()
    embedding = client.embed_texts([query])[0]
    params = _build_db_params()
    with connect_postgres(params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    title,
                    problem,
                    resolution,
                    takeaway,
                    metadata,
                    1 - (embedding <=> %s::vector) AS score
                FROM task_memory
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector ASC
                LIMIT %s
                """,
                (_vector_literal(embedding), _vector_literal(embedding), top_k),
            )
            rows = cur.fetchall()

    lines: list[str] = []
    for title, problem, resolution, takeaway, metadata, score in rows:
        if float(score) < _TASK_MEMORY_SCORE_GATE:
            continue
        resolved_metadata = json.loads(metadata) if isinstance(metadata, str) else (metadata or {})
        tags = resolved_metadata.get("tags", [])
        lines.append(
            "\n".join(
                [
                    f"- 标题: {title or '未命名经验'}",
                    f"  score: {float(score):.2f}",
                    f"  problem: {problem}",
                    f"  resolution: {resolution}",
                    f"  takeaway: {takeaway or ''}",
                    f"  tags: {tags}",
                ]
            )
        )
    if not lines:
        return ""
    return "可复用 task_memory：\n" + "\n".join(lines)
