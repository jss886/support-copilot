from pathlib import Path
from typing import Iterable

from rag.embeddings import DashScopeEmbeddingClient
from rag.models import ChunkRecord
from rag.storage import save_index


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def split_text(
    text: str, chunk_size: int = 500, chunk_overlap: int = 100
) -> list[tuple[str, int, int]]:
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")

    chunks: list[tuple[str, int, int]] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append((chunk_text, start, end))
        if end >= text_length:
            break
        start = end - chunk_overlap

    return chunks


def batched(items: list[str], batch_size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), batch_size):
        yield items[index : index + batch_size]


def build_records_for_text(
    source: str,
    text: str,
    client: DashScopeEmbeddingClient,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    batch_size: int = 8,
    chunk_id_prefix: str | None = None,
) -> list[ChunkRecord]:
    raw_chunks = split_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunk_texts = [item[0] for item in raw_chunks]
    embeddings: list[list[float]] = []

    for text_batch in batched(chunk_texts, batch_size):
        embeddings.extend(client.embed_texts(text_batch))

    prefix = chunk_id_prefix or Path(source).stem or "chunk"
    return [
        ChunkRecord(
            chunk_id=f"{prefix}-chunk-{idx}",
            source=source,
            text=chunk_text,
            start=start,
            end=end,
            embedding=embedding,
        )
        for idx, ((chunk_text, start, end), embedding) in enumerate(
            zip(raw_chunks, embeddings)
        )
    ]


def build_index(
    source_path: Path,
    output_path: Path,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    batch_size: int = 8,
) -> list[ChunkRecord]:
    client = DashScopeEmbeddingClient()
    records = build_records_for_text(
        source=str(source_path),
        text=load_text(source_path),
        client=client,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        batch_size=batch_size,
        chunk_id_prefix="chunk",
    )
    save_index(records, output_path)
    return records


def build_index_for_directory(
    source_dir: Path,
    output_path: Path,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    batch_size: int = 8,
) -> list[ChunkRecord]:
    if not source_dir.is_dir():
        raise ValueError(f"Source directory does not exist: {source_dir}")

    source_paths = sorted(path for path in source_dir.rglob("*.md") if path.is_file())
    if not source_paths:
        raise ValueError(f"No markdown files found under: {source_dir}")

    client = DashScopeEmbeddingClient()
    all_records: list[ChunkRecord] = []

    for source_path in source_paths:
        all_records.extend(
            build_records_for_text(
                source=str(source_path),
                text=load_text(source_path),
                client=client,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                batch_size=batch_size,
            )
        )

    save_index(all_records, output_path)
    return all_records

