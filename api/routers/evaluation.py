from pathlib import Path

from fastapi import APIRouter, Query

from api.common import translate_exception
from api.schemas import (
    RagasEvaluationResponse,
    RagasEvaluationResult,
    RetrievalEvaluationResponse,
    RetrievalEvaluationResult,
)
from rag.config import PROJECT_ROOT
from rag.eval.dataset import DEFAULT_EVAL_DATASET
from rag.eval.evaluator import evaluate_retrieval
from rag.eval.ragas_evaluator import (
    DEFAULT_RAGAS_OUTPUT,
    evaluate_ragas_metrics,
    resolve_ragas_output_path,
)

router = APIRouter(prefix="/api/v1/evaluation", tags=["评测"])
DEFAULT_RETRIEVAL_EVAL_WORKERS = 6
DEFAULT_RAGAS_EVAL_TOP_K = 5
DEFAULT_RAGAS_EVAL_LIMIT = 20


# 作用：把相对数据集路径统一解析到项目根目录下，避免接口调用方关心服务进程工作目录。
def _resolve_dataset_path(dataset_path: str | Path) -> Path:
    path = Path(dataset_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved_path = path.resolve()
    if not resolved_path.exists():
        raise ValueError(f"评测集不存在：{resolved_path}")
    return resolved_path


# 作用：执行默认检索离线评测，并返回 Recall@5 与 MRR 聚合结果。
@router.get(
    "/retrieval",
    response_model=RetrievalEvaluationResponse,
    summary="评测检索 Recall 和 MRR",
)
def evaluate_retrieval_metrics() -> RetrievalEvaluationResponse:
    try:
        resolved_dataset_path = _resolve_dataset_path(DEFAULT_EVAL_DATASET)
        metrics = evaluate_retrieval(
            dataset_path=resolved_dataset_path,
            workers=DEFAULT_RETRIEVAL_EVAL_WORKERS,
        )
    except Exception as exc:
        raise translate_exception(exc) from exc

    return RetrievalEvaluationResponse(
        data=RetrievalEvaluationResult(
            dataset_path=str(resolved_dataset_path),
            total=metrics.total,
            recall_at_5=metrics.recall_at_5,
            mrr=metrics.mrr,
        ),
        message="检索评测完成。",
    )


# 作用：执行默认 RAGAS 离线评测，并返回忠实度、相关性和上下文质量指标。
@router.get(
    "/ragas",
    response_model=RagasEvaluationResponse,
    summary="评测 RAGAS 四项核心指标",
)
def evaluate_ragas_summary(
    limit: int = Query(default=DEFAULT_RAGAS_EVAL_LIMIT, ge=1, description="本次评测最多处理多少条样本。"),
    top_k: int = Query(default=DEFAULT_RAGAS_EVAL_TOP_K, ge=1, description="每条问题最多带入回答链路的检索片段数。"),
) -> RagasEvaluationResponse:
    try:
        resolved_dataset_path = _resolve_dataset_path(DEFAULT_EVAL_DATASET)
        resolved_output_path = resolve_ragas_output_path(PROJECT_ROOT / DEFAULT_RAGAS_OUTPUT)
        result = evaluate_ragas_metrics(
            dataset_path=resolved_dataset_path,
            top_k=top_k,
            limit=limit,
            output_path=resolved_output_path,
        )
    except Exception as exc:
        raise translate_exception(exc) from exc

    return RagasEvaluationResponse(
        data=RagasEvaluationResult(
            dataset_path=result["dataset_path"],
            sample_count=result["sample_count"],
            top_k=result["top_k"],
            faithfulness=result["faithfulness"],
            response_relevancy=result["response_relevancy"],
            context_recall=result["context_recall"],
            context_precision=result["context_precision"],
            output_path=result["output_path"],
        ),
        message=f"RAGAS 评测完成，共处理 {result['sample_count']} 条样本。",
    )
