import argparse
import json
from pathlib import Path


# 作用：定位默认评测集文件，统一复用当前评测目录下的 manual_eval_set.json。
DEFAULT_DATASET_PATH = Path(__file__).resolve().parent / "manual_eval_set.json"


# 作用：解析命令行参数，只要求填写问题、参考答案和一组或多组证据。
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="向手工评测集追加一条评测样本。")
    parser.add_argument(
        "--question",
        required=True,
        help="评测问题。",
    )
    parser.add_argument(
        "--ground-truth",
        required=True,
        help="这条问题对应的标准答案或参考答案。",
    )
    parser.add_argument(
        "--evidence",
        action="append",
        nargs=2,
        metavar=("DB_CHUNK_ID", "SOURCE"),
        required=True,
        help="追加一条目标证据，格式为：--evidence <db_chunk_id> <source>，可重复传多次。",
    )
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET_PATH),
        help="评测集文件路径，默认写入当前目录下的 manual_eval_set.json。",
    )
    return parser.parse_args()


# 作用：读取现有评测集内容，不存在时自动初始化为空列表。
def load_dataset(dataset_path: Path) -> list[dict]:
    if not dataset_path.exists():
        return []
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"评测集格式不正确，期望 JSON 数组：{dataset_path}")
    return payload


# 作用：根据已有样本数量生成一个连续的 case_id，避免手工维护编号。
def build_next_item_id(items: list[dict]) -> str:
    max_index = 0
    for item in items:
        item_id = str(item.get("item_id", "")).strip()
        if not item_id.startswith("case_"):
            continue
        suffix = item_id.removeprefix("case_")
        if suffix.isdigit():
            max_index = max(max_index, int(suffix))
    return f"case_{max_index + 1:03d}"


# 作用：把命令行输入转换成评测集样本结构，并顺手去掉重复证据。
def build_item(args: argparse.Namespace, item_id: str) -> dict:
    seen_pairs: set[tuple[str, str]] = set()
    evidences: list[dict[str, str]] = []
    for chunk_id, source in args.evidence:
        normalized_chunk_id = chunk_id.strip()
        normalized_source = source.strip()
        if not normalized_chunk_id or not normalized_source:
            continue
        pair = (normalized_chunk_id, normalized_source)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        evidences.append(
            {
                "db_chunk_id": normalized_chunk_id,
                "source": normalized_source,
            }
        )

    if not evidences:
        raise ValueError("至少需要提供一条有效 evidence。")

    return {
        "item_id": item_id,
        "question": args.question.strip(),
        "ground_truth": args.ground_truth.strip(),
        "expected_evidences": evidences,
    }


# 作用：把新增样本写回评测集文件，默认保持 utf-8 和缩进格式便于后续人工查看。
def save_dataset(dataset_path: Path, items: list[dict]) -> None:
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# 作用：串联整个追加流程，并在控制台输出新增结果，方便用户立刻确认。
def main() -> None:
    args = parse_args()
    dataset_path = Path(args.dataset).resolve()
    items = load_dataset(dataset_path)
    item_id = build_next_item_id(items)
    item = build_item(args, item_id=item_id)
    items.append(item)
    save_dataset(dataset_path, items)
    print(f"已写入评测样本：{item_id}")
    print(f"评测集路径：{dataset_path}")


if __name__ == "__main__":
    main()
