import json

from rag.config import settings
from rag.db import connect_postgres, parse_jdbc_postgres_url
from rag.embeddings import DashScopeEmbeddingClient
from rag.models import ChunkRecord


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


def _build_chunk_record(content: str, metadata: dict) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=metadata.get("chunk_id", ""),
        source=metadata.get("source", ""),
        text=content,
        start=metadata.get("start", 0),
        end=metadata.get("end", 0),
        embedding=[],
        metadata=metadata,
    )


def retrieve(
    query: str,
    top_k: int = 3,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
    source: str | None = None,
    embedding_dimensions: int | None = None,
) -> list[tuple[float, ChunkRecord]]:
    resolved_jdbc_url, resolved_db_user, resolved_db_password = _resolve_db_config(
        jdbc_url, db_user, db_password
    )
    client = DashScopeEmbeddingClient(
        dimensions=embedding_dimensions or settings.dashscope.default_dimensions or 1536
    )
    query_embedding = client.embed_texts([query])[0]
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
    """
    sql_params: list[object] = [_vector_literal(query_embedding)]

    if source:
        sql += " WHERE d.source = %s"
        sql_params.append(source)

    sql += " ORDER BY c.embedding <=> %s::vector ASC LIMIT %s"
    sql_params.extend([_vector_literal(query_embedding), top_k])

    with connect_postgres(params) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, sql_params)
            rows = cur.fetchall()

    results: list[tuple[float, ChunkRecord]] = []
    for content, metadata, score in rows:
        resolved_metadata = metadata
        if isinstance(resolved_metadata, str):
            resolved_metadata = json.loads(resolved_metadata)
        results.append((float(score), _build_chunk_record(content, resolved_metadata or {})))

    return results
