import math
from pathlib import Path

from rag.embeddings import DashScopeEmbeddingClient
from rag.models import ChunkRecord
from rag.storage import load_index


def cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def retrieve(
    query: str, index_path: Path, top_k: int = 3
) -> list[tuple[float, ChunkRecord]]:
    client = DashScopeEmbeddingClient()
    query_embedding = client.embed_texts([query])[0]
    records = load_index(index_path)

    scored = [
        (cosine_similarity(query_embedding, record.embedding), record)
        for record in records
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:top_k]
