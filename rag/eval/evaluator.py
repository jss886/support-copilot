from dataclasses import dataclass
from pathlib import Path

from rag.config import settings
from rag.db import connect_postgres, parse_jdbc_postgres_url
from rag.embeddings import DashScopeEmbeddingClient
from rag.eval.dataset import load_eval_dataset
from rag.eval.generator import DEFAULT_EVAL_DATASET


@dataclass(frozen=True)
class RetrievalMetrics:
    total: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    mrr: float


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


def _resolve_db_config(
    jdbc_url: str | None,
    db_user: str | None,
    db_password: str | None,
) -> tuple[str, str, str]:
    resolved_jdbc_url = jdbc_url or settings.postgres.jdbc_url
    resolved_db_user = db_user or settings.postgres.user
    resolved_db_password = db_password or settings.postgres.password
    if not resolved_jdbc_url or not resolved_db_user or not resolved_db_password:
        raise ValueError(
            "Missing PostgreSQL config. Set jdbc_url/db_user/db_password via CLI, "
            "config_local.py, config.py, or environment variables."
        )
    return resolved_jdbc_url, resolved_db_user, resolved_db_password


def _match_item(expected_source: str, expected_substrings: list[str], source: str, text: str) -> bool:
    if source != expected_source:
        return False
    if not expected_substrings:
        return True
    return any(snippet in text for snippet in expected_substrings)


def evaluate_retrieval(
    dataset_path: Path = DEFAULT_EVAL_DATASET,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
    embedding_dimensions: int | None = None,
) -> RetrievalMetrics:
    items = load_eval_dataset(dataset_path)
    max_k = 10
    hits = {1: 0, 3: 0, 5: 0, 10: 0}
    reciprocal_rank_total = 0.0

    resolved_jdbc_url, resolved_db_user, resolved_db_password = _resolve_db_config(
        jdbc_url, db_user, db_password
    )
    client = DashScopeEmbeddingClient(
        dimensions=embedding_dimensions or settings.dashscope.default_dimensions or 1536
    )
    params = parse_jdbc_postgres_url(
        resolved_jdbc_url,
        user=resolved_db_user,
        password=resolved_db_password,
    )

    sql = """
        SELECT
            c.content,
            c.metadata,
            1 - (c.embedding <=> %s::vector) AS score
        FROM kb_chunks c
        JOIN kb_documents d ON d.id = c.document_id
        ORDER BY c.embedding <=> %s::vector ASC
        LIMIT %s
    """

    with connect_postgres(params) as conn:
        with conn.cursor() as cur:
            for item in items:
                query_embedding = client.embed_texts([item.question])[0]
                vector_literal = _vector_literal(query_embedding)
                cur.execute(sql, (vector_literal, vector_literal, max_k))
                rows = cur.fetchall()

                first_hit_rank: int | None = None
                for rank, (content, metadata, _) in enumerate(rows, start=1):
                    resolved_metadata = metadata or {}
                    source = resolved_metadata.get("source", "")
                    if _match_item(
                        expected_source=item.expected_source,
                        expected_substrings=item.expected_substrings,
                        source=source,
                        text=content,
                    ):
                        first_hit_rank = rank
                        break

                if first_hit_rank is not None:
                    reciprocal_rank_total += 1.0 / first_hit_rank
                    for k in hits:
                        if first_hit_rank <= k:
                            hits[k] += 1

    total = len(items)
    return RetrievalMetrics(
        total=total,
        recall_at_1=hits[1] / total if total else 0.0,
        recall_at_3=hits[3] / total if total else 0.0,
        recall_at_5=hits[5] / total if total else 0.0,
        recall_at_10=hits[10] / total if total else 0.0,
        mrr=reciprocal_rank_total / total if total else 0.0,
    )

