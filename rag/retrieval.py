import json

from rag.config import settings
from rag.db import PostgresConnectionParams, connect_postgres, parse_jdbc_postgres_url
from rag.embeddings import DashScopeEmbeddingClient
from rag.models import ChunkRecord
from rag.text_search import build_segmented_search_text, extract_query_keywords


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


# 作用：统一解析数据库配置，并补齐连接超时，避免检索阶段长时间阻塞。
def _resolve_db_config(
    jdbc_url: str | None,
    db_user: str | None,
    db_password: str | None,
) -> tuple[str, str, str, int]:
    resolved_jdbc_url = jdbc_url or settings.postgres.jdbc_url
    resolved_db_user = db_user or settings.postgres.user
    resolved_db_password = db_password or settings.postgres.password
    if not resolved_jdbc_url or not resolved_db_user or not resolved_db_password:
        raise ValueError(
            "Missing PostgreSQL config. Set jdbc_url/db_user/db_password via CLI, "
            "config_local.py, config.py, or environment variables."
        )
    return (
        resolved_jdbc_url,
        resolved_db_user,
        resolved_db_password,
        settings.postgres.connect_timeout,
    )


# 作用：把数据库中的文本和元数据组装成统一的切片对象，方便上层复用。
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


# 作用：统一解析数据库返回的 metadata，兼容 psycopg 直接返 dict 和字符串两种情况。
def _normalize_metadata(metadata: dict | str | None) -> dict:
    if metadata is None:
        return {}
    if isinstance(metadata, str):
        return json.loads(metadata)
    return metadata


# 作用：生成来源过滤子句，避免向量检索和关键词检索重复拼接条件。
def _build_source_filter_clause(source: str | None, sql_params: list[object]) -> str:
    if not source:
        return ""
    sql_params.append(source)
    return " WHERE d.source = %s"


# 作用：执行向量召回，负责找出语义上最相近的切片。
def _retrieve_vector(
    query_embedding: list[float],
    *,
    top_k: int,
    source: str | None,
    params: PostgresConnectionParams,
) -> list[tuple[float, ChunkRecord]]:
    sql_params: list[object] = [_vector_literal(query_embedding)]
    source_clause = _build_source_filter_clause(source, sql_params)
    sql = f"""
        SELECT
            c.content,
            c.metadata,
            1 - (c.embedding <=> %s::vector) AS score
        FROM kb_chunks c
        JOIN kb_documents d ON d.id = c.document_id
        {source_clause}
        ORDER BY c.embedding <=> %s::vector ASC
        LIMIT %s
    """
    sql_params.extend([_vector_literal(query_embedding), top_k])

    with connect_postgres(params) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, sql_params)
            rows = cur.fetchall()

    results: list[tuple[float, ChunkRecord]] = []
    for content, metadata, score in rows:
        resolved_metadata = _normalize_metadata(metadata)
        results.append((float(score), _build_chunk_record(content, resolved_metadata)))
    return results


# 作用：执行关键词召回，先对查询做中文分词，再匹配分词后的 tsv。
def _retrieve_keyword(
    query: str,
    *,
    top_k: int,
    source: str | None,
    params: PostgresConnectionParams,
) -> list[tuple[float, ChunkRecord]]:
    query_keywords = extract_query_keywords(query)
    if not query_keywords:
        return []
    tsquery = " | ".join(query_keywords)
    if not tsquery:
        return []

    sql_params: list[object] = [tsquery]
    source_clause = _build_source_filter_clause(source, sql_params)
    if source_clause:
        where_clause = f"{source_clause} AND c.tsv @@ to_tsquery(%s)"
    else:
        where_clause = " WHERE c.tsv @@ to_tsquery(%s)"

    sql = f"""
        SELECT
            c.content,
            c.metadata,
            ts_rank_cd(c.tsv, to_tsquery(%s)) AS score
        FROM kb_chunks c
        JOIN kb_documents d ON d.id = c.document_id
        {where_clause}
        ORDER BY score DESC
        LIMIT %s
    """
    sql_params.extend([tsquery, top_k])

    with connect_postgres(params) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, sql_params)
            rows = cur.fetchall()

    results: list[tuple[float, ChunkRecord]] = []
    for content, metadata, score in rows:
        resolved_metadata = _normalize_metadata(metadata)
        results.append((float(score), _build_chunk_record(content, resolved_metadata)))
    return results


# 作用：用 RRF 融合两路召回结果，避免直接混加不同量纲的原始分数。
def _fuse_with_rrf(
    vector_results: list[tuple[float, ChunkRecord]],
    keyword_results: list[tuple[float, ChunkRecord]],
    *,
    top_k: int,
    rrf_k: int = 60,
    vector_weight: float = 1.0,
    keyword_weight: float = 0.5,
) -> list[tuple[float, ChunkRecord]]:
    merged_scores: dict[str, float] = {}
    merged_records: dict[str, ChunkRecord] = {}

    for rank, (_, record) in enumerate(vector_results, start=1):
        key = record.chunk_id or f"{record.source}:{record.start}:{record.end}"
        merged_scores[key] = merged_scores.get(key, 0.0) + vector_weight / (rrf_k + rank)
        merged_records.setdefault(key, record)

    for rank, (_, record) in enumerate(keyword_results, start=1):
        key = record.chunk_id or f"{record.source}:{record.start}:{record.end}"
        merged_scores[key] = merged_scores.get(key, 0.0) + keyword_weight / (rrf_k + rank)
        merged_records.setdefault(key, record)

    ranked_keys = sorted(merged_scores, key=lambda key: merged_scores[key], reverse=True)
    return [(merged_scores[key], merged_records[key]) for key in ranked_keys[:top_k]]


# 作用：执行混合检索，组合向量召回、关键词召回和 RRF 融合后的最终结果。
def retrieve(
    query: str,
    top_k: int = 3,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
    source: str | None = None,
    embedding_dimensions: int | None = None,
) -> list[tuple[float, ChunkRecord]]:
    resolved_jdbc_url, resolved_db_user, resolved_db_password, connect_timeout = _resolve_db_config(
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
        connect_timeout=connect_timeout,
    )

    # 这里多取一批候选再融合，避免两路召回彼此挤掉有效结果。
    candidate_top_k = max(top_k * 4, 10)
    vector_results = _retrieve_vector(
        query_embedding,
        top_k=candidate_top_k,
        source=source,
        params=params,
    )
    keyword_results = _retrieve_keyword(
        query,
        top_k=candidate_top_k,
        source=source,
        params=params,
    )
    return _fuse_with_rrf(vector_results, keyword_results, top_k=top_k)


