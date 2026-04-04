import argparse
from pathlib import Path

from rag.answering import answer_question
from rag.config import DEFAULT_INDEX_FILE
from rag.indexing import build_index, build_index_for_directory
from rag.retrieval import retrieve


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal single-document RAG demo.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser(
        "index", help="Chunk a document and build embeddings."
    )
    index_parser.add_argument("--source", required=True, help="Path to the source document.")
    index_parser.add_argument(
        "--index-file",
        default=DEFAULT_INDEX_FILE,
        help="Where to store the local embedding index.",
    )
    index_parser.add_argument("--chunk-size", type=int, default=500)
    index_parser.add_argument("--chunk-overlap", type=int, default=100)
    index_parser.add_argument("--batch-size", type=int, default=8)

    index_dir_parser = subparsers.add_parser(
        "index-dir", help="Chunk markdown files in a directory and build embeddings."
    )
    index_dir_parser.add_argument(
        "--source-dir", required=True, help="Directory containing markdown files."
    )
    index_dir_parser.add_argument(
        "--index-file",
        default=DEFAULT_INDEX_FILE,
        help="Where to store the local embedding index.",
    )
    index_dir_parser.add_argument("--chunk-size", type=int, default=500)
    index_dir_parser.add_argument("--chunk-overlap", type=int, default=100)
    index_dir_parser.add_argument("--batch-size", type=int, default=8)

    query_parser = subparsers.add_parser(
        "query", help="Query against the local embedding index."
    )
    query_parser.add_argument(
        "--question", required=True, help="User question for retrieval."
    )
    query_parser.add_argument(
        "--index-file",
        default=DEFAULT_INDEX_FILE,
        help="Path to the local embedding index.",
    )
    query_parser.add_argument("--top-k", type=int, default=3)

    answer_parser = subparsers.add_parser(
        "answer", help="Retrieve chunks and generate a final answer."
    )
    answer_parser.add_argument(
        "--question", required=True, help="User question for RAG answering."
    )
    answer_parser.add_argument(
        "--index-file",
        default=DEFAULT_INDEX_FILE,
        help="Path to the local embedding index.",
    )
    answer_parser.add_argument("--top-k", type=int, default=3)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "index":
        records = build_index(
            source_path=Path(args.source),
            output_path=Path(args.index_file),
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            batch_size=args.batch_size,
        )
        print(f"Indexed {len(records)} chunks into {Path(args.index_file).resolve()}")
        return

    if args.command == "index-dir":
        records = build_index_for_directory(
            source_dir=Path(args.source_dir),
            output_path=Path(args.index_file),
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            batch_size=args.batch_size,
        )
        print(f"Indexed {len(records)} chunks into {Path(args.index_file).resolve()}")
        return

    if args.command == "query":
        results = retrieve(
            query=args.question,
            index_path=Path(args.index_file),
            top_k=args.top_k,
        )
        for rank, (score, record) in enumerate(results, start=1):
            print(
                f"[{rank}] score={score:.4f} source={record.source} "
                f"range=({record.start}, {record.end})"
            )
            print(record.text)
            print("-" * 80)
        return

    if args.command == "answer":
        answer = answer_question(
            question=args.question,
            index_path=Path(args.index_file),
            top_k=args.top_k,
        )
        print(answer)
        return

    raise ValueError(f"Unsupported command: {args.command}")
