import argparse
import sys
from pathlib import Path

# 作用：兼容直接以脚本路径运行时的导入路径，避免出现找不到 rag 包的问题。
if __package__ in (None, ""):
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    project_root_str = str(PROJECT_ROOT)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

from rag.eval.dataset import DEFAULT_EVAL_DATASET
from rag.eval.evaluator import evaluate_retrieval
from rag.eval.ragas_evaluator import (
    DEFAULT_RAGAS_OUTPUT,
    evaluate_ragas_metrics,
    resolve_ragas_output_path,
)


# 作用：解析评测命令行参数，统一管理检索评测和 RAGAS 评测入口。
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG retrieval evaluation utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate_parser = subparsers.add_parser("evaluate", help="Evaluate retrieval recall metrics.")
    evaluate_parser.add_argument(
        "--dataset",
        default=str(DEFAULT_EVAL_DATASET),
        help="Eval dataset path.",
    )
    evaluate_parser.add_argument("--jdbc-url", help="Optional JDBC PostgreSQL url override.")
    evaluate_parser.add_argument("--db-user", help="Optional PostgreSQL user override.")
    evaluate_parser.add_argument("--db-password", help="Optional PostgreSQL password override.")
    evaluate_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        help="Optional embedding dimension override.",
    )
    evaluate_parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="How many concurrent workers to use during retrieval evaluation.",
    )
    evaluate_parser.add_argument(
        "--candidate-top-k",
        type=int,
        default=20,
        help="How many hybrid candidates to keep before rerank.",
    )
    evaluate_parser.add_argument(
        "--disable-rerank",
        action="store_true",
        help="Disable rerank and evaluate hybrid retrieval directly.",
    )
    evaluate_parser.add_argument(
        "--disable-query-rewrite",
        action="store_true",
        help="Disable query rewrite and evaluate only the original query.",
    )

    ragas_parser = subparsers.add_parser(
        "evaluate-ragas",
        help="Evaluate answer-level metrics with RAGAS.",
    )
    ragas_parser.add_argument(
        "--dataset",
        default=str(DEFAULT_EVAL_DATASET),
        help="Eval dataset path.",
    )
    ragas_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="How many retrieved chunks to pass into the answer chain.",
    )
    ragas_parser.add_argument(
        "--limit",
        type=int,
        help="Optional sample limit to control time and API cost.",
    )
    ragas_parser.add_argument(
        "--output",
        default=str(DEFAULT_RAGAS_OUTPUT),
        help="Output path for aggregated RAGAS metrics.",
    )

    return parser.parse_args()


# 作用：根据子命令分发评测逻辑，并输出聚合结果。
def main() -> None:
    args = parse_args()

    if args.command == "evaluate":
        metrics = evaluate_retrieval(
            dataset_path=Path(args.dataset),
            jdbc_url=args.jdbc_url,
            db_user=args.db_user,
            db_password=args.db_password,
            embedding_dimensions=args.embedding_dimensions,
            workers=args.workers,
            candidate_top_k=args.candidate_top_k,
            use_rerank=not args.disable_rerank,
            use_query_rewrite=not args.disable_query_rewrite,
        )
        print(f"Total: {metrics.total}")
        print(f"Recall@5: {metrics.recall_at_5:.4f}")
        print(f"MRR: {metrics.mrr:.4f}")
        return

    if args.command == "evaluate-ragas":
        retrieval_metrics = evaluate_retrieval(dataset_path=Path(args.dataset))
        resolved_output_path = resolve_ragas_output_path(Path(args.output))
        result = evaluate_ragas_metrics(
            dataset_path=Path(args.dataset),
            top_k=args.top_k,
            limit=args.limit,
            output_path=resolved_output_path,
        )
        print(f"- 检索层：Recall@5 = {retrieval_metrics.recall_at_5:.4f}")
        print(f"- 排序层：MRR = {retrieval_metrics.mrr:.4f}")
        print(f"- 回答层：Faithfulness = {result['faithfulness']:.4f}")
        print(f"- 回答相关性：Response Relevancy = {result['response_relevancy']:.4f}")
        print(f"- 检索覆盖度：Context Recall = {result['context_recall']:.4f}")
        print(f"- 检索精度：Context Precision = {result['context_precision']:.4f}")
        print(f"- RAGAS 结果文件：{resolved_output_path}")
        return

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
