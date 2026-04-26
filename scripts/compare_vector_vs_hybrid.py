import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.config import settings
from rag.db import parse_jdbc_postgres_url
from rag.embeddings import DashScopeEmbeddingClient
from rag.eval.dataset import load_eval_dataset
from rag.retrieval import (
    _build_chunk_record,
    _fuse_with_rrf,
    _normalize_metadata,
    _resolve_db_config,
    _retrieve_keyword,
    _retrieve_vector,
)


# 作用：解析对比脚本参数，便于在同一评测集上比较纯向量与混合检索的排名差异。
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="比较纯向量检索与混合检索的排名差异。")
    parser.add_argument(
        "--dataset",
        default="resources/eval/feishu_kb_seed_eval_set_harder.json",
        help="评测集路径。",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="比较前多少条结果。",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="可选，仅对前 N 条样本做比较。",
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
        "--embedding-dimensions",
        type=int,
        default=settings.dashscope.default_dimensions or 1536,
        help="Embedding 维度。",
    )
    return parser.parse_args()


# 作用：判断召回结果是否命中预期文档，并用关键片段兜底校验命中质量。
def _match_item(expected_source: str, expected_substrings: list[str], source: str, text: str) -> bool:
    if source != expected_source:
        return False
    if not expected_substrings:
        return True
    return any(snippet in text for snippet in expected_substrings)


# 作用：找出一组结果里首个正确命中的排名，用于比较纯向量和混合检索是否真的改变了指标。
def _first_hit_rank(
    results: list[tuple[float, object]],
    *,
    expected_source: str,
    expected_substrings: list[str],
) -> int | None:
    for rank, (_, record) in enumerate(results, start=1):
        if _match_item(
            expected_source=expected_source,
            expected_substrings=expected_substrings,
            source=record.source,
            text=record.text,
        ):
            return rank
    return None


# 作用：格式化结果来源，便于在差异样本里快速观察是哪个文档导致了排名变化。
def _sources(results: list[tuple[float, object]]) -> list[str]:
    return [record.source for _, record in results]


# 作用：比较纯向量与混合检索在同一 query 上的首个命中排名和 topK 来源列表。
def main() -> None:
    args = parse_args()
    items = load_eval_dataset(Path(args.dataset))
    if args.limit:
        items = items[: args.limit]

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

    changed_topk_count = 0
    changed_hit_rank_count = 0
    keyword_non_empty_count = 0
    changed_examples: list[dict] = []

    for item in items:
        query_embedding = client.embed_texts([item.question])[0]
        vector_results = _retrieve_vector(
            query_embedding,
            top_k=args.top_k,
            source=None,
            params=params,
        )
        keyword_results = _retrieve_keyword(
            item.question,
            top_k=args.top_k,
            source=None,
            params=params,
        )
        hybrid_results = _fuse_with_rrf(
            vector_results,
            keyword_results,
            top_k=args.top_k,
        )

        if keyword_results:
            keyword_non_empty_count += 1

        vector_sources = _sources(vector_results)
        hybrid_sources = _sources(hybrid_results)
        if vector_sources != hybrid_sources:
            changed_topk_count += 1

        vector_hit_rank = _first_hit_rank(
            vector_results,
            expected_source=item.expected_source,
            expected_substrings=item.expected_substrings,
        )
        hybrid_hit_rank = _first_hit_rank(
            hybrid_results,
            expected_source=item.expected_source,
            expected_substrings=item.expected_substrings,
        )
        if vector_hit_rank != hybrid_hit_rank:
            changed_hit_rank_count += 1
            if len(changed_examples) < 10:
                changed_examples.append(
                    {
                        "item_id": item.item_id,
                        "question": item.question,
                        "vector_hit_rank": vector_hit_rank,
                        "hybrid_hit_rank": hybrid_hit_rank,
                        "vector_sources": vector_sources,
                        "keyword_sources": _sources(keyword_results),
                        "hybrid_sources": hybrid_sources,
                    }
                )

    print(f"Total: {len(items)}")
    print(f"Keyword non-empty count: {keyword_non_empty_count}")
    print(f"TopK source list changed count: {changed_topk_count}")
    print(f"First-hit rank changed count: {changed_hit_rank_count}")
    print("Changed examples:")
    print(json.dumps(changed_examples, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
