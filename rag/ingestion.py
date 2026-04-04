import json
import uuid
from pathlib import Path

from rag.config import settings
from rag.db import connect_postgres, parse_jdbc_postgres_url
from rag.embeddings import DashScopeEmbeddingClient
from rag.feishu_loader import load_feishu_document
from rag.indexing import build_records_for_text, load_text
from rag.models import ChunkRecord


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


def _insert_document(
    jdbc_url: str,
    db_user: str,
    db_password: str,
    title: str,
    source: str,
    doc_type: str,
    tags: dict,
    records: list[ChunkRecord],
) -> tuple[str, int]:
    params = parse_jdbc_postgres_url(jdbc_url, user=db_user, password=db_password)
    document_id = str(uuid.uuid4())

    with connect_postgres(params) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM kb_documents WHERE source = %s", (source,))
            cur.execute(
                """
                INSERT INTO kb_documents (
                    id, doc_name, doc_type, title, source, tags
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    document_id,
                    title,
                    doc_type,
                    title,
                    source,
                    json.dumps(tags, ensure_ascii=False),
                ),
            )

            for chunk_index, record in enumerate(records):
                cur.execute(
                    """
                    INSERT INTO kb_chunks (
                        id,
                        document_id,
                        chunk_index,
                        content,
                        token_count,
                        tsv,
                        embedding,
                        metadata
                    ) VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        to_tsvector(%s, %s),
                        %s::vector,
                        %s::jsonb
                    )
                    """,
                    (
                        str(uuid.uuid4()),
                        document_id,
                        chunk_index,
                        record.text,
                        len(record.text),
                        settings.postgres.text_search_config,
                        record.text,
                        _vector_literal(record.embedding),
                        json.dumps(
                            {
                                "chunk_id": record.chunk_id,
                                "source": record.source,
                                "start": record.start,
                                "end": record.end,
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )

        conn.commit()

    return document_id, len(records)


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


def _resolve_rag_config(
    chunk_size: int | None,
    chunk_overlap: int | None,
    batch_size: int | None,
) -> tuple[int, int, int]:
    return (
        chunk_size or settings.rag.chunk_size,
        chunk_overlap or settings.rag.chunk_overlap,
        batch_size or settings.rag.batch_size,
    )


def _build_records(
    source: str,
    text: str,
    chunk_id_prefix: str | None,
    embedding_dimensions: int,
    chunk_size: int | None,
    chunk_overlap: int | None,
    batch_size: int | None,
) -> list[ChunkRecord]:
    resolved_chunk_size, resolved_chunk_overlap, resolved_batch_size = _resolve_rag_config(
        chunk_size, chunk_overlap, batch_size
    )
    client = DashScopeEmbeddingClient(dimensions=embedding_dimensions)
    return build_records_for_text(
        source=source,
        text=text,
        client=client,
        chunk_size=resolved_chunk_size,
        chunk_overlap=resolved_chunk_overlap,
        batch_size=resolved_batch_size,
        chunk_id_prefix=chunk_id_prefix,
    )


def ingest_text_to_db(
    *,
    title: str,
    source: str,
    doc_type: str,
    text: str,
    tags: dict | None = None,
    chunk_id_prefix: str | None = None,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    batch_size: int | None = None,
    embedding_dimensions: int = 1536,
) -> tuple[str, int]:
    resolved_jdbc_url, resolved_db_user, resolved_db_password = _resolve_db_config(
        jdbc_url, db_user, db_password
    )
    records = _build_records(
        source=source,
        text=text,
        chunk_id_prefix=chunk_id_prefix,
        embedding_dimensions=embedding_dimensions,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        batch_size=batch_size,
    )
    return _insert_document(
        jdbc_url=resolved_jdbc_url,
        db_user=resolved_db_user,
        db_password=resolved_db_password,
        title=title,
        source=source,
        doc_type=doc_type,
        tags=tags or {},
        records=records,
    )


def ingest_file_to_db(
    source_path: Path,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    batch_size: int | None = None,
    embedding_dimensions: int = 1536,
) -> tuple[str, int]:
    source = str(source_path)
    return ingest_text_to_db(
        title=source_path.stem,
        source=source,
        doc_type="local_file",
        text=load_text(source_path),
        tags={"path": source},
        chunk_id_prefix=source_path.stem,
        jdbc_url=jdbc_url,
        db_user=db_user,
        db_password=db_password,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        batch_size=batch_size,
        embedding_dimensions=embedding_dimensions,
    )


def ingest_directory_to_db(
    source_dir: Path,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    batch_size: int | None = None,
    embedding_dimensions: int = 1536,
) -> tuple[int, int]:
    if not source_dir.is_dir():
        raise ValueError(f"Source directory does not exist: {source_dir}")

    source_paths = sorted(path for path in source_dir.rglob("*.md") if path.is_file())
    if not source_paths:
        raise ValueError(f"No markdown files found under: {source_dir}")

    document_count = 0
    chunk_count = 0
    for source_path in source_paths:
        _, inserted_chunks = ingest_file_to_db(
            source_path=source_path,
            jdbc_url=jdbc_url,
            db_user=db_user,
            db_password=db_password,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            batch_size=batch_size,
            embedding_dimensions=embedding_dimensions,
        )
        document_count += 1
        chunk_count += inserted_chunks

    return document_count, chunk_count


def ingest_feishu_doc_to_db(
    doc_id: str,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    batch_size: int | None = None,
    embedding_dimensions: int = 1536,
) -> tuple[str, int]:
    document = load_feishu_document(doc_id=doc_id)
    source = f"feishu://docx/{doc_id}"
    return ingest_text_to_db(
        title=document.title,
        source=source,
        doc_type="feishu_docx",
        text=document.text,
        tags={
            "doc_id": doc_id,
            "revision_id": document.revision_id,
            "image_ocr_count": document.image_ocr_count,
            "table_count": document.table_count,
            "attachment_count": document.attachment_count,
        },
        chunk_id_prefix=doc_id,
        jdbc_url=jdbc_url,
        db_user=db_user,
        db_password=db_password,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        batch_size=batch_size,
        embedding_dimensions=embedding_dimensions,
    )
