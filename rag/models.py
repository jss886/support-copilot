from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChunkRecord:
    # 作用：承载单个切片的检索结果，既保留业务 chunk_id，也保留数据库主键便于评测和排障。
    db_chunk_id: str
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
