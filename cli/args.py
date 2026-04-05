import argparse

from rag.config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal single-document RAG demo.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser(
        "index", help="Chunk a document and write embeddings into PostgreSQL."
    )
    index_parser.add_argument("--source", required=True, help="Path to the source document.")
    index_parser.add_argument("--chunk-size", type=int, default=settings.rag.chunk_size)
    index_parser.add_argument(
        "--chunk-overlap", type=int, default=settings.rag.chunk_overlap
    )
    index_parser.add_argument("--batch-size", type=int, default=settings.rag.batch_size)
    index_parser.add_argument(
        "--jdbc-url", default=settings.postgres.jdbc_url, help="JDBC PostgreSQL url."
    )
    index_parser.add_argument(
        "--db-user", default=settings.postgres.user, help="Database user."
    )
    index_parser.add_argument(
        "--db-password", default=settings.postgres.password, help="Database password."
    )
    index_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=settings.dashscope.default_dimensions or 1536,
    )

    index_dir_parser = subparsers.add_parser(
        "index-dir", help="Chunk markdown files in a directory and write embeddings into PostgreSQL."
    )
    index_dir_parser.add_argument(
        "--source-dir", required=True, help="Directory containing markdown files."
    )
    index_dir_parser.add_argument(
        "--chunk-size", type=int, default=settings.rag.chunk_size
    )
    index_dir_parser.add_argument(
        "--chunk-overlap", type=int, default=settings.rag.chunk_overlap
    )
    index_dir_parser.add_argument(
        "--batch-size", type=int, default=settings.rag.batch_size
    )
    index_dir_parser.add_argument(
        "--jdbc-url", default=settings.postgres.jdbc_url, help="JDBC PostgreSQL url."
    )
    index_dir_parser.add_argument(
        "--db-user", default=settings.postgres.user, help="Database user."
    )
    index_dir_parser.add_argument(
        "--db-password", default=settings.postgres.password, help="Database password."
    )
    index_dir_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=settings.dashscope.default_dimensions or 1536,
    )

    index_feishu_parser = subparsers.add_parser(
        "index-feishu", help="Load a Feishu docx document and write embeddings into PostgreSQL."
    )
    index_feishu_parser.add_argument(
        "--doc-id", required=True, help="Feishu docx document id."
    )
    index_feishu_parser.add_argument(
        "--chunk-size", type=int, default=settings.rag.chunk_size
    )
    index_feishu_parser.add_argument(
        "--chunk-overlap", type=int, default=settings.rag.chunk_overlap
    )
    index_feishu_parser.add_argument(
        "--batch-size", type=int, default=settings.rag.batch_size
    )
    index_feishu_parser.add_argument(
        "--jdbc-url", default=settings.postgres.jdbc_url, help="JDBC PostgreSQL url."
    )
    index_feishu_parser.add_argument(
        "--db-user", default=settings.postgres.user, help="Database user."
    )
    index_feishu_parser.add_argument(
        "--db-password", default=settings.postgres.password, help="Database password."
    )
    index_feishu_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=settings.dashscope.default_dimensions or 1536,
    )

    index_feishu_db_parser = subparsers.add_parser(
        "index-feishu-db",
        help="Load a Feishu docx document and write chunks into PostgreSQL.",
    )
    index_feishu_db_parser.add_argument(
        "--doc-id", required=True, help="Feishu docx document id."
    )
    index_feishu_db_parser.add_argument(
        "--jdbc-url", default=settings.postgres.jdbc_url, help="JDBC PostgreSQL url."
    )
    index_feishu_db_parser.add_argument(
        "--db-user", default=settings.postgres.user, help="Database user."
    )
    index_feishu_db_parser.add_argument(
        "--db-password", default=settings.postgres.password, help="Database password."
    )
    index_feishu_db_parser.add_argument(
        "--chunk-size", type=int, default=settings.rag.chunk_size
    )
    index_feishu_db_parser.add_argument(
        "--chunk-overlap", type=int, default=settings.rag.chunk_overlap
    )
    index_feishu_db_parser.add_argument(
        "--batch-size", type=int, default=settings.rag.batch_size
    )
    index_feishu_db_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=settings.dashscope.default_dimensions or 1536,
    )

    index_feishu_space_parser = subparsers.add_parser(
        "index-feishu-space",
        help="Recursively load docx documents under a Feishu wiki parent node and write chunks into PostgreSQL.",
    )
    index_feishu_space_parser.add_argument(
        "--space-id", required=True, help="Feishu wiki space id."
    )
    index_feishu_space_parser.add_argument(
        "--parent-node-token", required=True, help="Feishu wiki parent node token."
    )
    index_feishu_space_parser.add_argument(
        "--jdbc-url", default=settings.postgres.jdbc_url, help="JDBC PostgreSQL url."
    )
    index_feishu_space_parser.add_argument(
        "--db-user", default=settings.postgres.user, help="Database user."
    )
    index_feishu_space_parser.add_argument(
        "--db-password", default=settings.postgres.password, help="Database password."
    )
    index_feishu_space_parser.add_argument(
        "--chunk-size", type=int, default=settings.rag.chunk_size
    )
    index_feishu_space_parser.add_argument(
        "--chunk-overlap", type=int, default=settings.rag.chunk_overlap
    )
    index_feishu_space_parser.add_argument(
        "--batch-size", type=int, default=settings.rag.batch_size
    )
    index_feishu_space_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=settings.dashscope.default_dimensions or 1536,
    )

    seed_parser = subparsers.add_parser(
        "seed-test-data",
        help="Generate synthetic support documents and write chunked data into PostgreSQL.",
    )
    seed_parser.add_argument("--doc-count", type=int, default=100)
    seed_parser.add_argument("--chunks-per-doc", type=int, default=5)
    seed_parser.add_argument(
        "--jdbc-url", default=settings.postgres.jdbc_url, help="JDBC PostgreSQL url."
    )
    seed_parser.add_argument(
        "--db-user", default=settings.postgres.user, help="Database user."
    )
    seed_parser.add_argument(
        "--db-password", default=settings.postgres.password, help="Database password."
    )
    seed_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=settings.dashscope.default_dimensions or 1536,
    )

    seed_hard_negative_parser = subparsers.add_parser(
        "seed-hard-negatives",
        help="Generate similar-but-wrong distractor documents and write them into PostgreSQL.",
    )
    seed_hard_negative_parser.add_argument(
        "--jdbc-url", default=settings.postgres.jdbc_url, help="JDBC PostgreSQL url."
    )
    seed_hard_negative_parser.add_argument(
        "--db-user", default=settings.postgres.user, help="Database user."
    )
    seed_hard_negative_parser.add_argument(
        "--db-password", default=settings.postgres.password, help="Database password."
    )
    seed_hard_negative_parser.add_argument(
        "--chunk-size", type=int, default=settings.rag.chunk_size
    )
    seed_hard_negative_parser.add_argument(
        "--chunk-overlap", type=int, default=settings.rag.chunk_overlap
    )
    seed_hard_negative_parser.add_argument(
        "--batch-size", type=int, default=settings.rag.batch_size
    )
    seed_hard_negative_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=settings.dashscope.default_dimensions or 1536,
    )

    query_parser = subparsers.add_parser("query", help="Query against PostgreSQL chunks.")
    query_parser.add_argument(
        "--question", required=True, help="User question for retrieval."
    )
    query_parser.add_argument("--top-k", type=int, default=3)
    query_parser.add_argument(
        "--jdbc-url", default=settings.postgres.jdbc_url, help="JDBC PostgreSQL url."
    )
    query_parser.add_argument(
        "--db-user", default=settings.postgres.user, help="Database user."
    )
    query_parser.add_argument(
        "--db-password", default=settings.postgres.password, help="Database password."
    )
    query_parser.add_argument("--source", help="Optional source filter, for example feishu://docx/<doc_id>.")
    query_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=settings.dashscope.default_dimensions or 1536,
    )

    answer_parser = subparsers.add_parser("answer", help="Retrieve PostgreSQL chunks and generate a final answer.")
    answer_parser.add_argument(
        "--question", required=True, help="User question for RAG answering."
    )
    answer_parser.add_argument("--top-k", type=int, default=3)
    answer_parser.add_argument(
        "--jdbc-url", default=settings.postgres.jdbc_url, help="JDBC PostgreSQL url."
    )
    answer_parser.add_argument(
        "--db-user", default=settings.postgres.user, help="Database user."
    )
    answer_parser.add_argument(
        "--db-password", default=settings.postgres.password, help="Database password."
    )
    answer_parser.add_argument("--source", help="Optional source filter, for example feishu://docx/<doc_id>.")
    answer_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=settings.dashscope.default_dimensions or 1536,
    )

    return parser.parse_args()
