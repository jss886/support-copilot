"""Minimal RAG utilities for the support-copilot project."""

from rag.answering import answer_question
from rag.db import PostgresConnectionParams, connect_postgres, parse_jdbc_postgres_url
from rag.embeddings import DashScopeEmbeddingClient
from rag.feishu_loader import (
    FeishuDocument,
    FeishuWikiNode,
    list_feishu_wiki_nodes,
    list_feishu_wiki_subtree_docx_nodes,
    load_feishu_document,
    load_feishu_file,
)
from rag.hard_negative_data import generate_hard_negative_docs, seed_hard_negative_docs_to_db
from rag.ingestion import (
    ingest_directory_to_db,
    ingest_feishu_doc_to_db,
    ingest_feishu_file_to_db,
    ingest_feishu_wiki_subtree_to_db,
    ingest_file_to_db,
)
from rag.indexing import (
    build_index,
    build_index_for_directory,
    build_index_for_feishu_doc,
    split_text,
)
from rag.models import ChunkRecord
from rag.reranking import rerank_chunks
from rag.retrieval import retrieve, retrieve_hybrid_candidates

__all__ = [
    "ChunkRecord",
    "DashScopeEmbeddingClient",
    "FeishuDocument",
    "FeishuWikiNode",
    "PostgresConnectionParams",
    "answer_question",
    "build_index",
    "build_index_for_directory",
    "build_index_for_feishu_doc",
    "connect_postgres",
    "generate_hard_negative_docs",
    "ingest_directory_to_db",
    "ingest_feishu_doc_to_db",
    "ingest_feishu_file_to_db",
    "ingest_feishu_wiki_subtree_to_db",
    "ingest_file_to_db",
    "list_feishu_wiki_nodes",
    "list_feishu_wiki_subtree_docx_nodes",
    "load_feishu_document",
    "load_feishu_file",
    "parse_jdbc_postgres_url",
    "rerank_chunks",
    "retrieve",
    "retrieve_hybrid_candidates",
    "seed_hard_negative_docs_to_db",
    "split_text",
]
