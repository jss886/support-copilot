"""Minimal RAG utilities for the support-copilot project."""
from rag.answering import answer_question
from rag.embeddings import DashScopeEmbeddingClient
from rag.indexing import build_index, build_index_for_directory, split_text
from rag.models import ChunkRecord
from rag.retrieval import retrieve

__all__ = [
    "ChunkRecord",
    "DashScopeEmbeddingClient",
    "answer_question",
    "build_index",
    "build_index_for_directory",
    "retrieve",
    "split_text",
]
