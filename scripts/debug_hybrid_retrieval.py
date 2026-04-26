import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.config import settings
from rag.db import parse_jdbc_postgres_url
from rag.embeddings import DashScopeEmbeddingClient
from rag.retrieval import (
    _fuse_with_rrf,
    _resolve_db_config,
    _retrieve_keyword,
    _retrieve_vector,
)
from rag.text_search import build_segmented_search_text


# 作用：解析调试命令参数，便于单独观察一条 query 在混合检索各阶段的表现。
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="调试混合检索各阶段结果。")
    parser.add_argument(
        "--question",
        required=True,
        help="要调试的用户问题。",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="每一路展示多少条结果。",
    )
    parser.add_argument(
        "--jdbc-url",
        default=settings.postgres.jdbc_url,
        help="PostgreSQL JDBC 连接串。",
    )
    parser.add_argument(
        "--db-user",
        default=settings.postgres.user,
        help="PostgreSQL 用户名。",
    )
    parser.add_argument(
        "--db-password",
        default=settings.postgres.password,
        help="PostgreSQL 密码。",
    )
    parser.add_argument(
        "--source",
        help="可选来源过滤。",
    )
    parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=settings.dashscope.default_dimensions or 1536,
        help="Embedding 维度。",
    )
    return parser.parse_args()


# 作用：格式化打印单路召回结果，便于快速对比排名、来源和片段内容。
def _print_results(title: str, results: list[tuple[float, object]]) -> None:
    print(f"\n=== {title} ===")
    if not results:
        print("无结果")
        return
    for rank, (score, record) in enumerate(results, start=1):
        print(
            f"[{rank}] score={score:.4f} source={record.source} "
            f"range=({record.start}, {record.end})"
        )
        print(record.text[:200].replace("\n", " "))


# 作用：执行一条 query 的分阶段调试，帮助判断问题出在关键词召回还是融合排序。
def main() -> None:
    args = parse_args()
    segmented_query = build_segmented_search_text(args.question)
    print(f"原始问题: {args.question}")
    print(f"分词结果: {segmented_query}")

    jdbc_url, db_user, db_password, connect_timeout = _resolve_db_config(
        args.jdbc_url,
        args.db_user,
        args.db_password,
    )
    params = parse_jdbc_postgres_url(
        jdbc_url,
        user=db_user,
        password=db_password,
        connect_timeout=connect_timeout,
    )

    client = DashScopeEmbeddingClient(dimensions=args.embedding_dimensions)
    query_embedding = client.embed_texts([args.question])[0]
    vector_results = _retrieve_vector(
        query_embedding,
        top_k=args.top_k,
        source=args.source,
        params=params,
    )
    keyword_results = _retrieve_keyword(
        args.question,
        top_k=args.top_k,
        source=args.source,
        params=params,
    )
    rrf_results = _fuse_with_rrf(
        vector_results,
        keyword_results,
        top_k=args.top_k,
    )

    _print_results("向量召回", vector_results)
    _print_results("关键词召回", keyword_results)
    _print_results("RRF 融合", rrf_results)


if __name__ == "__main__":
    main()
