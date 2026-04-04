import json
from dataclasses import asdict
from pathlib import Path

from rag.models import ChunkRecord


def save_index(records: list[ChunkRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_index(index_path: Path) -> list[ChunkRecord]:
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    return [ChunkRecord(**item) for item in payload]
