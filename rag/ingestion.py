import json
import uuid
from pathlib import Path

from rag.config import settings
from rag.db import connect_postgres, parse_jdbc_postgres_url
from rag.embeddings import DashScopeEmbeddingClient
from rag.feishu_loader import load_feishu_document, list_feishu_wiki_subtree_docx_nodes
from rag.indexing import build_records_for_text, load_text
from rag.models import ChunkRecord, SourceElement
from rag.text_search import build_chunk_search_text, extract_search_keywords


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


# 作用：构建切片写库时用于全文检索的分词文本，把标题、来源和标签等高价值字段一并纳入召回。
def _build_chunk_search_payload(
    *,
    title: str,
    source: str,
    tags: dict,
    record: ChunkRecord,
) -> str:
    return build_chunk_search_text(
        title=title,
        source=source,
        content=record.text,
        keywords=[],
        tags=tags,
        metadata={
            "chunk_id": record.chunk_id,
            "source": record.source,
            "start": record.start,
            "end": record.end,
            **record.metadata,
        },
    )


# 作用：覆盖同一 source 的旧文档，并把新切片连同向量和分词后的 tsv 一起写入数据库。
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
                metadata = {
                    "chunk_id": record.chunk_id,
                    "source": record.source,
                    "start": record.start,
                    "end": record.end,
                    **record.metadata,
                }
                segmented_search_text = _build_chunk_search_payload(
                    title=title,
                    source=source,
                    tags=tags,
                    record=record,
                )
                search_keywords = extract_search_keywords(segmented_search_text)
                cur.execute(
                    """
                    INSERT INTO kb_chunks (
                        id,
                        document_id,
                        chunk_index,
                        content,
                        token_count,
                        keywords,
                        tsv,
                        embedding,
                        metadata
                    ) VALUES (
                        %s,
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
                        search_keywords,
                        settings.postgres.text_search_config,
                        segmented_search_text,
                        _vector_literal(record.embedding),
                        json.dumps(metadata, ensure_ascii=False),
                    ),
                )

        conn.commit()

    return document_id, len(records)


# 作用：解析数据库连接配置，保证所有入库入口都复用同一套配置解析逻辑。
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


# 作用：解析切片和批处理配置，避免多处重复读取 settings。
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


# 作用：对原始文本执行切片并补齐 embedding，作为统一的入库前处理步骤。
def _build_records(
    source: str,
    text: str,
    chunk_id_prefix: str | None,
    embedding_dimensions: int,
    chunk_size: int | None,
    chunk_overlap: int | None,
    batch_size: int | None,
    elements: list[SourceElement] | None = None,
) -> list[ChunkRecord]:
    resolved_chunk_size, resolved_chunk_overlap, resolved_batch_size = _resolve_rag_config(
        chunk_size, chunk_overlap, batch_size
    )
    client = DashScopeEmbeddingClient(dimensions=embedding_dimensions)
    return build_records_for_text(
        source=source,
        text=text,
        elements=elements,
        client=client,
        chunk_size=resolved_chunk_size,
        chunk_overlap=resolved_chunk_overlap,
        batch_size=resolved_batch_size,
        chunk_id_prefix=chunk_id_prefix,
    )


# 作用：把任意文本内容切片后写入 kb_documents 和 kb_chunks。
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
    elements: list[SourceElement] | None = None,
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
        elements=elements,
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


# 作用：把已经切好片并带 embedding 的记录直接写入数据库。
def ingest_chunk_records_to_db(
    *,
    title: str,
    source: str,
    doc_type: str,
    records: list[ChunkRecord],
    tags: dict | None = None,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
) -> tuple[str, int]:
    resolved_jdbc_url, resolved_db_user, resolved_db_password = _resolve_db_config(
        jdbc_url, db_user, db_password
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


# 作用：读取单个本地文件并完成切片、向量化和入库。
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


# 作用：批量导入目录下的 markdown 文件。
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


# 作用：读取单篇飞书文档并将切片写入 PostgreSQL。
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
        elements=document.elements,
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


# 作用：递归导入指定飞书知识库父节点下的全部 docx 文档。
def ingest_feishu_wiki_subtree_to_db(
    *,
    space_id: str,
    parent_node_token: str,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    batch_size: int | None = None,
    embedding_dimensions: int = 1536,
) -> tuple[int, int]:
    nodes = list_feishu_wiki_subtree_docx_nodes(
        space_id=space_id,
        parent_node_token=parent_node_token,
    )
    if not nodes:
        raise ValueError(
            f"No docx documents found under space_id={space_id}, parent_node_token={parent_node_token}"
        )

    document_count = 0
    chunk_count = 0
    for node in nodes:
        if not node.obj_token:
            continue
        # 这里复用单文档导入逻辑，确保批量导入与手动导入在切片、元数据和检索文本构建上保持一致。
        _, inserted_chunks = ingest_feishu_doc_to_db(
            doc_id=node.obj_token,
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
