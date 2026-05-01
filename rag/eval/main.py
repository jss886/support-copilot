import argparse
from pathlib import Path

from rag.eval.evaluator import evaluate_retrieval
from rag.eval.hard_generator import (
    DEFAULT_HARD_EVAL_DATASET,
    DEFAULT_HARDER_EVAL_DATASET,
    generate_hard_feishu_seed_eval_dataset,
    generate_harder_feishu_seed_eval_dataset,
    rewrite_hard_eval_sources_from_manifest,
    rewrite_harder_eval_sources_from_manifest,
)
from rag.eval.generator import DEFAULT_EVAL_DATASET, generate_eval_dataset
from rag.eval.ragas_evaluator import (
    DEFAULT_RAGAS_OUTPUT,
    evaluate_ragas_metrics,
    resolve_ragas_output_path,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG retrieval evaluation utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="Generate a retrieval eval dataset.")
    generate_parser.add_argument(
        "--source-dir",
        default="resources/doc",
        help="Directory containing markdown files used to generate eval items.",
    )
    generate_parser.add_argument(
        "--output",
        default=str(DEFAULT_EVAL_DATASET),
        help="Output dataset path.",
    )
    generate_parser.add_argument(
        "--count",
        type=int,
        default=500,
        help="Target number of eval items to generate.",
    )

    generate_hard_parser = subparsers.add_parser(
        "generate-hard",
        help="Generate a harder eval dataset for the Feishu seed knowledge base.",
    )
    generate_hard_parser.add_argument(
        "--output",
        default=str(DEFAULT_HARD_EVAL_DATASET),
        help="Output dataset path.",
    )
    generate_hard_parser.add_argument(
        "--manifest",
        default="resources/testdata/feishu_kb_seed/manifest.json",
        help="Manifest path used to map topic code to feishu://docx/<id> source.",
    )

    generate_harder_parser = subparsers.add_parser(
        "generate-harder",
        help="Generate an even harder eval dataset with noisier user-style queries.",
    )
    generate_harder_parser.add_argument(
        "--output",
        default=str(DEFAULT_HARDER_EVAL_DATASET),
        help="Output dataset path.",
    )
    generate_harder_parser.add_argument(
        "--manifest",
        default="resources/testdata/feishu_kb_seed/manifest.json",
        help="Manifest path used to map topic code to feishu://docx/<id> source.",
    )

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
        default=str(DEFAULT_HARDER_EVAL_DATASET),
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


def main() -> None:
    args = parse_args()

    if args.command == "generate":
        items = generate_eval_dataset(
            source_dir=Path(args.source_dir),
            output_path=Path(args.output),
            target_count=args.count,
        )
        print(f"Generated {len(items)} eval items into {Path(args.output).resolve()}")
        return

    if args.command == "generate-hard":
        generate_hard_feishu_seed_eval_dataset(output_path=Path(args.output))
        items = rewrite_hard_eval_sources_from_manifest(
            manifest_path=Path(args.manifest),
            dataset_path=Path(args.output),
        )
        print(f"Generated {len(items)} hard eval items into {Path(args.output).resolve()}")
        return

    if args.command == "generate-harder":
        generate_harder_feishu_seed_eval_dataset(output_path=Path(args.output))
        items = rewrite_harder_eval_sources_from_manifest(
            manifest_path=Path(args.manifest),
            dataset_path=Path(args.output),
        )
        print(f"Generated {len(items)} harder eval items into {Path(args.output).resolve()}")
        return

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
        print(f"Recall@1: {metrics.recall_at_1:.4f}")
        print(f"Recall@3: {metrics.recall_at_3:.4f}")
        print(f"Recall@5: {metrics.recall_at_5:.4f}")
        print(f"Recall@10: {metrics.recall_at_10:.4f}")
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
        print(f"- 检索层：Recall@1 = {retrieval_metrics.recall_at_1:.4f}")
        print(f"- 检索层：Recall@3 = {retrieval_metrics.recall_at_3:.4f}")
        print(f"- 检索层：Recall@5 = {retrieval_metrics.recall_at_5:.4f}")
        print(f"- 检索层：Recall@10 = {retrieval_metrics.recall_at_10:.4f}")
        print(f"- 排序层：MRR = {retrieval_metrics.mrr:.4f}")
        print(f"- 回答层：Faithfulness = {result['faithfulness']:.4f}")
        print(f"- 回答相关性：Response Relevancy = {result['response_relevancy']:.4f}")
        print(f"- 检索覆盖度：Context Recall = {result['context_recall']:.4f}")
        print(f"- RAGAS 结果文件：{resolved_output_path}")
        return

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
