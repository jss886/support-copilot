from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from rag.eval.dataset import load_eval_dataset
from rag.eval.generator import DEFAULT_EVAL_DATASET
from rag.eval.models import EvalItem
from rag.retrieval import retrieve


@dataclass(frozen=True)
class RetrievalMetrics:
    total: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    mrr: float


# 作用：判断召回结果是否命中预期文档，并用关键片段兜底校验命中质量。
def _match_item(expected_source: str, expected_substrings: list[str], source: str, text: str) -> bool:
    if source != expected_source:
        return False
    if not expected_substrings:
        return True
    return any(snippet in text for snippet in expected_substrings)


# 作用：评估单条样本在当前检索链路中的首个命中排名，便于在线程池中并发执行。
def _evaluate_item(
    item: EvalItem,
    *,
    max_k: int,
    jdbc_url: str | None,
    db_user: str | None,
    db_password: str | None,
    embedding_dimensions: int | None,
) -> int | None:
    results = retrieve(
        query=item.question,
        top_k=max_k,
        jdbc_url=jdbc_url,
        db_user=db_user,
        db_password=db_password,
        embedding_dimensions=embedding_dimensions,
    )

    for rank, (_, record) in enumerate(results, start=1):
        if _match_item(
            expected_source=item.expected_source,
            expected_substrings=item.expected_substrings,
            source=record.source,
            text=record.text,
        ):
            return rank
    return None


# 作用：评估当前检索链路的 Recall@K 和 MRR，默认直接复用线上混合检索逻辑。
def evaluate_retrieval(
    dataset_path: Path = DEFAULT_EVAL_DATASET,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
    embedding_dimensions: int | None = None,
    workers: int = 6,
) -> RetrievalMetrics:
    items = load_eval_dataset(dataset_path)
    max_k = 10
    hits = {1: 0, 3: 0, 5: 0, 10: 0}
    reciprocal_rank_total = 0.0

    resolved_workers = max(1, workers)
    with ThreadPoolExecutor(max_workers=resolved_workers) as executor:
        ranks = list(
            executor.map(
                lambda item: _evaluate_item(
                    item,
                    max_k=max_k,
                    jdbc_url=jdbc_url,
                    db_user=db_user,
                    db_password=db_password,
                    embedding_dimensions=embedding_dimensions,
                ),
                items,
            )
        )

    for first_hit_rank in ranks:
        if first_hit_rank is None:
            continue
        reciprocal_rank_total += 1.0 / first_hit_rank
        for k in hits:
            if first_hit_rank <= k:
                hits[k] += 1

    total = len(items)
    return RetrievalMetrics(
        total=total,
        recall_at_1=hits[1] / total if total else 0.0,
        recall_at_3=hits[3] / total if total else 0.0,
        recall_at_5=hits[5] / total if total else 0.0,
        recall_at_10=hits[10] / total if total else 0.0,
        mrr=reciprocal_rank_total / total if total else 0.0,
    )
