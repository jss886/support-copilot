from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from rag.eval.dataset import DEFAULT_EVAL_DATASET, load_eval_dataset
from rag.eval.models import EvalItem
from rag.retrieval import retrieve


@dataclass(frozen=True)
class RetrievalMetrics:
    # 作用：承载检索层评测结果，当前只关注 Recall@5 和 MRR 两个核心指标。
    total: int
    recall_at_5: float
    mrr: float


@dataclass(frozen=True)
class RetrievalEvalResult:
    # 作用：承载单条样本的检索评测结果，便于同时计算 Recall@5 和 MRR。
    recall_at_5: float
    first_hit_rank: int | None


# 作用：抽取单条样本的目标数据库主键集合，统一去重并过滤空值。
def _build_expected_db_chunk_ids(item: EvalItem) -> list[str]:
    seen: set[str] = set()
    chunk_ids: list[str] = []
    for evidence in item.expected_evidences:
        chunk_id = evidence.db_chunk_id.strip()
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        chunk_ids.append(chunk_id)
    return chunk_ids


# 作用：校验检索评测样本是否满足新结构要求，避免旧数据集被静默算成 0 分。
def _validate_retrieval_item(item: EvalItem) -> None:
    if not item.expected_evidences:
        raise ValueError(
            f"Eval item {item.item_id} is missing expected_evidences; "
            "the new retrieval evaluation requires chunk-level labels."
        )


# 作用：评估单条样本的 Recall@5 和首个命中排名，严格按 chunk_id 做匹配。
def _evaluate_item(
    item: EvalItem,
    *,
    max_k: int,
    jdbc_url: str | None,
    db_user: str | None,
    db_password: str | None,
    embedding_dimensions: int | None,
    candidate_top_k: int | None,
    use_rerank: bool | None,
    use_query_rewrite: bool | None,
) -> RetrievalEvalResult:
    _validate_retrieval_item(item)
    expected_chunk_ids = _build_expected_db_chunk_ids(item)
    if not expected_chunk_ids:
        return RetrievalEvalResult(recall_at_5=0.0, first_hit_rank=None)

    target_chunk_ids = set(expected_chunk_ids)
    results = retrieve(
        query=item.question,
        top_k=max_k,
        jdbc_url=jdbc_url,
        db_user=db_user,
        db_password=db_password,
        embedding_dimensions=embedding_dimensions,
        candidate_top_k=candidate_top_k,
        use_rerank=use_rerank,
        use_query_rewrite=use_query_rewrite,
    )

    matched_top5: set[str] = set()
    first_hit_rank: int | None = None
    for rank, (_, record) in enumerate(results, start=1):
        chunk_id = record.db_chunk_id.strip()
        if not chunk_id or chunk_id not in target_chunk_ids:
            continue
        if rank <= 5:
            matched_top5.add(chunk_id)
        if first_hit_rank is None:
            first_hit_rank = rank

    return RetrievalEvalResult(
        recall_at_5=len(matched_top5) / len(expected_chunk_ids),
        first_hit_rank=first_hit_rank,
    )


# 作用：评估当前检索链路的 Recall@5 和 MRR，默认复用线上检索逻辑。
def evaluate_retrieval(
    dataset_path: Path = DEFAULT_EVAL_DATASET,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
    embedding_dimensions: int | None = None,
    workers: int = 6,
    candidate_top_k: int | None = None,
    use_rerank: bool | None = None,
    use_query_rewrite: bool | None = None,
) -> RetrievalMetrics:
    items = load_eval_dataset(dataset_path)
    max_k = 10
    recall_at_5_total = 0.0
    reciprocal_rank_total = 0.0

    resolved_workers = max(1, workers)
    with ThreadPoolExecutor(max_workers=resolved_workers) as executor:
        results = list(
            executor.map(
                lambda item: _evaluate_item(
                    item,
                    max_k=max_k,
                    jdbc_url=jdbc_url,
                    db_user=db_user,
                    db_password=db_password,
                    embedding_dimensions=embedding_dimensions,
                    candidate_top_k=candidate_top_k,
                    use_rerank=use_rerank,
                    use_query_rewrite=use_query_rewrite,
                ),
                items,
            )
        )

    for result in results:
        recall_at_5_total += result.recall_at_5
        first_hit_rank = result.first_hit_rank
        if first_hit_rank is None:
            continue
        reciprocal_rank_total += 1.0 / first_hit_rank

    total = len(items)
    return RetrievalMetrics(
        total=total,
        recall_at_5=recall_at_5_total / total if total else 0.0,
        mrr=reciprocal_rank_total / total if total else 0.0,
    )
