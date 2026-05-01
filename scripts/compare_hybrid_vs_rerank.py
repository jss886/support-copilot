import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.eval.dataset import load_eval_dataset
from rag.retrieval import retrieve, retrieve_hybrid_candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="比较 hybrid 结果和 rerank 结果的差异。")
    parser.add_argument(
        "--dataset",
        default="resources/eval/feishu_kb_seed_eval_set_harder.json",
        help="评测集路径。",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="只比较前多少条样本。",
    )
    parser.add_argument(
        "--candidate-top-k",
        type=int,
        default=20,
        help="混合召回候选数量。",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="最终输出结果数量。",
    )
    return parser.parse_args()


def _sources(results: list[tuple[float, object]]) -> list[str]:
    # 作用：提取结果来源列表，便于快速观察排序前后命中文档是否变化。
    return [record.source for _, record in results]


def _first_hit_rank(
    results: list[tuple[float, object]],
    *,
    expected_source: str,
    expected_substrings: list[str],
) -> int | None:
    # 作用：找出首个正确命中的位置，便于比较 rerank 是否真正提升了排序。
    for rank, (_, record) in enumerate(results, start=1):
        if record.source != expected_source:
            continue
        if not expected_substrings or any(snippet in record.text for snippet in expected_substrings):
            return rank
    return None


def main() -> None:
    args = parse_args()
    items = load_eval_dataset(Path(args.dataset))
    items = items[: max(1, args.limit)]

    changed_count = 0
    improved_count = 0
    degraded_count = 0
    examples: list[dict] = []

    for item in items:
        hybrid_results = retrieve_hybrid_candidates(
            query=item.question,
            candidate_top_k=args.candidate_top_k,
        )[: args.top_k]
        rerank_results = retrieve(
            query=item.question,
            top_k=args.top_k,
            candidate_top_k=args.candidate_top_k,
            use_rerank=True,
        )

        hybrid_rank = _first_hit_rank(
            hybrid_results,
            expected_source=item.expected_source,
            expected_substrings=item.expected_substrings,
        )
        rerank_rank = _first_hit_rank(
            rerank_results,
            expected_source=item.expected_source,
            expected_substrings=item.expected_substrings,
        )
        if _sources(hybrid_results) != _sources(rerank_results):
            changed_count += 1
        if hybrid_rank != rerank_rank:
            if hybrid_rank is None or (rerank_rank is not None and rerank_rank < hybrid_rank):
                improved_count += 1
            elif rerank_rank is None or (hybrid_rank is not None and rerank_rank > hybrid_rank):
                degraded_count += 1

            if len(examples) < 10:
                examples.append(
                    {
                        "item_id": item.item_id,
                        "question": item.question,
                        "hybrid_rank": hybrid_rank,
                        "rerank_rank": rerank_rank,
                        "hybrid_sources": _sources(hybrid_results),
                        "rerank_sources": _sources(rerank_results),
                    }
                )

    print(f"Total compared: {len(items)}")
    print(f"Top{args.top_k} source changed count: {changed_count}")
    print(f"Improved first-hit rank count: {improved_count}")
    print(f"Degraded first-hit rank count: {degraded_count}")
    print("Examples:")
    print(json.dumps(examples, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
