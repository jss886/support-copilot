"""Minimal RAG utilities for the support-copilot project."""
from rag.answering import answer_question
from rag.db import PostgresConnectionParams, connect_postgres, parse_jdbc_postgres_url
from rag.embeddings import DashScopeEmbeddingClient
from rag.feishu_loader import FeishuDocument, load_feishu_document
from rag.ingestion import ingest_directory_to_db, ingest_feishu_doc_to_db, ingest_file_to_db
from rag.indexing import (
    build_index,
    build_index_for_directory,
    build_index_for_feishu_doc,
    split_text,
)
from rag.models import ChunkRecord
from rag.retrieval import retrieve

__all__ = [
    "ChunkRecord",
    "DashScopeEmbeddingClient",
    "FeishuDocument",
    "PostgresConnectionParams",
    "answer_question",
    "build_index",
    "build_index_for_directory",
    "build_index_for_feishu_doc",
    "connect_postgres",
    "ingest_directory_to_db",
    "ingest_feishu_doc_to_db",
    "ingest_file_to_db",
    "load_feishu_document",
    "parse_jdbc_postgres_url",
    "retrieve",
    "split_text",
]
