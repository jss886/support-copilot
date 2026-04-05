from pathlib import Path
from typing import Iterable

from rag.config import settings
from rag.embeddings import DashScopeEmbeddingClient
from rag.feishu_loader import load_feishu_document
from rag.models import ChunkRecord, SourceElement
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


def build_elements_from_text(text: str) -> list[SourceElement]:
    elements: list[SourceElement] = []
    lines = text.splitlines(keepends=True)
    title_path: list[str] = []
    paragraph_lines: list[str] = []
    paragraph_start: int | None = None
    paragraph_end = 0
    offset = 0

    def flush_paragraph() -> None:
        nonlocal paragraph_lines, paragraph_start, paragraph_end
        if not paragraph_lines or paragraph_start is None:
            paragraph_lines = []
            paragraph_start = None
            return
        paragraph_text = "\n".join(line.strip() for line in paragraph_lines if line.strip())
        if paragraph_text:
            elements.append(
                SourceElement(
                    text=paragraph_text,
                    start=paragraph_start,
                    end=paragraph_end,
                    element_type="text",
                    title_path=list(title_path),
                )
            )
        paragraph_lines = []
        paragraph_start = None

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        stripped = line.strip()
        line_start = offset
        line_end = offset + len(line)
        offset += len(raw_line)

        if not stripped:
            flush_paragraph()
            continue

        if stripped.startswith("#"):
            marker, _, heading_text = stripped.partition(" ")
            if marker and all(char == "#" for char in marker) and heading_text:
                flush_paragraph()
                level = len(marker)
                title_path = title_path[: level - 1]
                title_path.append(heading_text.strip())
                elements.append(
                    SourceElement(
                        text=heading_text.strip(),
                        start=line_start,
                        end=line_end,
                        element_type=f"heading{level}",
                        title_path=list(title_path),
                    )
                )
                continue

        if paragraph_start is None:
            paragraph_start = line_start
        paragraph_lines.append(line)
        paragraph_end = line_end

    flush_paragraph()

    if elements:
        return elements
    normalized_text = text.strip()
    if not normalized_text:
        return []
    return [
        SourceElement(
            text=normalized_text,
            start=0,
            end=len(normalized_text),
            element_type="text",
        )
    ]


def _normalize_elements(text: str, elements: list[SourceElement] | None) -> list[SourceElement]:
    return elements if elements else build_elements_from_text(text)


def _split_large_chunk(
    text: str,
    start: int,
    end: int,
    chunk_size: int,
    chunk_overlap: int,
    metadata: dict,
) -> list[tuple[str, int, int, dict]]:
    raw_chunks = split_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not raw_chunks:
        return []
    return [
        (
            chunk_text,
            start + relative_start,
            start + relative_end,
            dict(metadata),
        )
        for chunk_text, relative_start, relative_end in raw_chunks
    ]


def split_elements(
    elements: list[SourceElement],
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> list[tuple[str, int, int, dict]]:
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")

    chunks: list[tuple[str, int, int, dict]] = []
    current_texts: list[str] = []
    current_elements: list[SourceElement] = []
    current_start = 0
    current_end = 0
    current_length = 0

    def flush_chunk() -> None:
        nonlocal current_texts, current_elements, current_start, current_end, current_length
        if not current_elements:
            return
        text = "\n".join(current_texts).strip()
        if not text:
            current_texts = []
            current_elements = []
            current_length = 0
            return
        metadata = {
            "title_path": list(current_elements[-1].title_path),
            "element_types": [element.element_type for element in current_elements],
            "block_ids": [
                element.metadata["block_id"]
                for element in current_elements
                if element.metadata.get("block_id")
            ],
        }
        if len(text) > chunk_size:
            chunks.extend(
                _split_large_chunk(
                    text=text,
                    start=current_start,
                    end=current_end,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    metadata=metadata,
                )
            )
        else:
            chunks.append((text, current_start, current_end, metadata))
        current_texts = []
        current_elements = []
        current_length = 0

    for element in elements:
        element_text = element.text.strip()
        if not element_text:
            continue

        is_heading = element.element_type.startswith("heading")
        separator_length = 1 if current_texts else 0
        prospective_length = current_length + separator_length + len(element_text)

        if current_elements and (is_heading or prospective_length > chunk_size):
            flush_chunk()

        if not current_elements:
            current_start = element.start
            current_end = element.end
            current_length = 0

        if current_texts:
            current_length += 1
        current_texts.append(element_text)
        current_elements.append(element)
        current_end = element.end
        current_length += len(element_text)

    flush_chunk()
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
    elements: list[SourceElement] | None = None,
) -> list[ChunkRecord]:
    raw_chunks = split_elements(
        _normalize_elements(text, elements),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
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
            metadata=metadata,
        )
        for idx, ((chunk_text, start, end, metadata), embedding) in enumerate(
            zip(raw_chunks, embeddings)
        )
    ]


def build_index(
    source_path: Path,
    output_path: Path,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    batch_size: int | None = None,
) -> list[ChunkRecord]:
    client = DashScopeEmbeddingClient()
    records = build_records_for_text(
        source=str(source_path),
        text=load_text(source_path),
        client=client,
        chunk_size=chunk_size or settings.rag.chunk_size,
        chunk_overlap=chunk_overlap or settings.rag.chunk_overlap,
        batch_size=batch_size or settings.rag.batch_size,
        chunk_id_prefix="chunk",
    )
    save_index(records, output_path)
    return records


def build_index_for_directory(
    source_dir: Path,
    output_path: Path,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    batch_size: int | None = None,
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
                chunk_size=chunk_size or settings.rag.chunk_size,
                chunk_overlap=chunk_overlap or settings.rag.chunk_overlap,
                batch_size=batch_size or settings.rag.batch_size,
            )
        )

    save_index(all_records, output_path)
    return all_records


def build_index_for_feishu_doc(
    doc_id: str,
    output_path: Path,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    batch_size: int | None = None,
) -> list[ChunkRecord]:
    document = load_feishu_document(doc_id=doc_id)
    client = DashScopeEmbeddingClient()
    records = build_records_for_text(
        source=f"feishu://docx/{doc_id}",
        text=document.text,
        elements=document.elements,
        client=client,
        chunk_size=chunk_size or settings.rag.chunk_size,
        chunk_overlap=chunk_overlap or settings.rag.chunk_overlap,
        batch_size=batch_size or settings.rag.batch_size,
        chunk_id_prefix=doc_id,
    )
    save_index(records, output_path)
    return records
