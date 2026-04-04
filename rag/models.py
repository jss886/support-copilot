from dataclasses import dataclass


@dataclass
class ChunkRecord:
    chunk_id: str
    source: str
    text: str
    start: int
    end: int
    embedding: list[float]
