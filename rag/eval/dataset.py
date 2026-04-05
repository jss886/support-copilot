import json
from pathlib import Path

from rag.eval.models import EvalItem


def load_eval_dataset(dataset_path: Path) -> list[EvalItem]:
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    return [EvalItem(**item) for item in payload]


def save_eval_dataset(items: list[EvalItem], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
