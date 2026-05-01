from argparse import Namespace
from pathlib import Path

from rag.answering import answer_question
from rag.hard_negative_data import seed_hard_negative_docs_to_db
from rag.ingestion import (
    ingest_directory_to_db,
    ingest_feishu_doc_to_db,
    ingest_feishu_wiki_subtree_to_db,
    ingest_file_to_db,
)
from rag.retrieval import retrieve
from rag.synthetic_data import seed_synthetic_support_data


def _normalize_source_filter(source: str | None) -> str | None:
    """作用：远程 source 保持原样，本地 source 统一转成绝对路径字符串。"""
    if not source:
        return None
    if "://" in source:
        return source
    return str(Path(source))


def run_command(args: Namespace) -> None:
    if args.command == "index":
        document_id, chunk_count = ingest_file_to_db(
            source_path=Path(args.source),
            jdbc_url=args.jdbc_url,
            db_user=args.db_user,
            db_password=args.db_password,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            batch_size=args.batch_size,
            embedding_dimensions=args.embedding_dimensions,
        )
        print(f"Inserted document {document_id} with {chunk_count} chunks into PostgreSQL")
        return

    if args.command == "index-dir":
        document_count, chunk_count = ingest_directory_to_db(
            source_dir=Path(args.source_dir),
            jdbc_url=args.jdbc_url,
            db_user=args.db_user,
            db_password=args.db_password,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            batch_size=args.batch_size,
            embedding_dimensions=args.embedding_dimensions,
        )
        print(f"Inserted {document_count} documents with {chunk_count} chunks into PostgreSQL")
        return

    if args.command == "index-feishu":
        document_id, chunk_count = ingest_feishu_doc_to_db(
            doc_id=args.doc_id,
            jdbc_url=args.jdbc_url,
            db_user=args.db_user,
            db_password=args.db_password,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            batch_size=args.batch_size,
            embedding_dimensions=args.embedding_dimensions,
        )
        print(f"Inserted document {document_id} with {chunk_count} chunks into PostgreSQL")
        return

    if args.command == "index-feishu-db":
        document_id, chunk_count = ingest_feishu_doc_to_db(
            doc_id=args.doc_id,
            jdbc_url=args.jdbc_url,
            db_user=args.db_user,
            db_password=args.db_password,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            batch_size=args.batch_size,
            embedding_dimensions=args.embedding_dimensions,
        )
        print(f"Inserted document {document_id} with {chunk_count} chunks into PostgreSQL")
        return

    if args.command == "index-feishu-space":
        document_count, chunk_count = ingest_feishu_wiki_subtree_to_db(
            space_id=args.space_id,
            parent_node_token=args.parent_node_token,
            jdbc_url=args.jdbc_url,
            db_user=args.db_user,
            db_password=args.db_password,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            batch_size=args.batch_size,
            embedding_dimensions=args.embedding_dimensions,
        )
        print(
            f"Inserted {document_count} Feishu documents with {chunk_count} chunks into PostgreSQL"
        )
        return

    if args.command == "seed-test-data":
        document_count, chunk_count = seed_synthetic_support_data(
            doc_count=args.doc_count,
            chunks_per_doc=args.chunks_per_doc,
            jdbc_url=args.jdbc_url,
            db_user=args.db_user,
            db_password=args.db_password,
            embedding_dimensions=args.embedding_dimensions,
        )
        print(f"Inserted {document_count} synthetic documents with {chunk_count} chunks into PostgreSQL")
        return

    if args.command == "seed-hard-negatives":
        document_count, chunk_count = seed_hard_negative_docs_to_db(
            jdbc_url=args.jdbc_url,
            db_user=args.db_user,
            db_password=args.db_password,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            batch_size=args.batch_size,
            embedding_dimensions=args.embedding_dimensions,
        )
        print(
            f"Inserted {document_count} hard negative documents with {chunk_count} chunks into PostgreSQL"
        )
        return

    if args.command == "query":
        results = retrieve(
            query=args.question,
            top_k=args.top_k,
            jdbc_url=args.jdbc_url,
            db_user=args.db_user,
            db_password=args.db_password,
            source=_normalize_source_filter(args.source),
            embedding_dimensions=args.embedding_dimensions,
            candidate_top_k=args.candidate_top_k,
            use_rerank=not args.disable_rerank,
            use_query_rewrite=not args.disable_query_rewrite,
        )
        for rank, (score, record) in enumerate(results, start=1):
            print(
                f"[{rank}] score={score:.4f} source={record.source} "
                f"range=({record.start}, {record.end})"
            )
            print(record.text)
            print("-" * 80)
        return

    if args.command == "answer":
        answer = answer_question(
            question=args.question,
            top_k=args.top_k,
            jdbc_url=args.jdbc_url,
            db_user=args.db_user,
            db_password=args.db_password,
            source=_normalize_source_filter(args.source),
            embedding_dimensions=args.embedding_dimensions,
            candidate_top_k=args.candidate_top_k,
            use_rerank=not args.disable_rerank,
            use_query_rewrite=not args.disable_query_rewrite,
        )
        print(answer)
        return

    raise ValueError(f"Unsupported command: {args.command}")
