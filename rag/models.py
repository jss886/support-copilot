from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChunkRecord:
    chunk_id: str
    source: str
    text: str
    start: int
    end: int
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceElement:
    text: str
    start: int
    end: int
    element_type: str = "text"
    title_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
