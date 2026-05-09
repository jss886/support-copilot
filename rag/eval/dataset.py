import json
from pathlib import Path

from rag.eval.models import EvalItem, ExpectedEvidence


DEFAULT_EVAL_DATASET = Path(__file__).resolve().parent / "manual_eval_set.json"


def load_eval_dataset(dataset_path: Path) -> list[EvalItem]:
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    items: list[EvalItem] = []
    for item in payload:
        expected_evidences: list[ExpectedEvidence] = []
        for evidence in item.get("expected_evidences", []):
            if isinstance(evidence, ExpectedEvidence):
                expected_evidences.append(evidence)
                continue
            expected_evidences.append(
                ExpectedEvidence(
                    db_chunk_id=evidence.get("db_chunk_id") or evidence.get("chunk_id", ""),
                    source=evidence.get("source", ""),
                )
            )
        items.append(
            EvalItem(
                item_id=item["item_id"],
                question=item["question"],
                expected_evidences=expected_evidences,
                ground_truth=item.get("ground_truth", ""),
                doc_title=item.get("doc_title", ""),
                section_title=item.get("section_title"),
                expected_source=item.get("expected_source", ""),
                expected_substrings=item.get("expected_substrings", []),
            )
        )
    return items


def save_eval_dataset(items: list[EvalItem], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
