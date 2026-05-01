from pathlib import Path
from threading import Lock

from FlagEmbedding import FlagReranker

from rag.config import PROJECT_ROOT, settings
from rag.models import ChunkRecord

_RERANK_LOCK = Lock()
_RERANKER_CACHE: dict[tuple[str, int, int], FlagReranker] = {}


def _resolve_model_path(model_path: str | None) -> str:
    # 作用：统一解析 reranker 模型路径，兼容相对路径和配置默认值。
    resolved_path = Path(model_path or settings.rag.reranker_model_path)
    if not resolved_path.is_absolute():
        resolved_path = PROJECT_ROOT / resolved_path
    if not resolved_path.exists():
        raise ValueError(f"Reranker model path does not exist: {resolved_path}")
    return str(resolved_path)


def _get_reranker(
    model_path: str,
    batch_size: int,
    max_length: int,
) -> FlagReranker:
    # 作用：按模型配置缓存本地 reranker 实例，避免重复加载大模型。
    cache_key = (model_path, batch_size, max_length)
    with _RERANK_LOCK:
        reranker = _RERANKER_CACHE.get(cache_key)
        if reranker is None:
            reranker = FlagReranker(
                model_name_or_path=model_path,
                use_fp16=False,
                devices="cpu",
                batch_size=batch_size,
                max_length=max_length,
                normalize=True,
            )
            _RERANKER_CACHE[cache_key] = reranker
        return reranker


def rerank_chunks(
    query: str,
    candidates: list[tuple[float, ChunkRecord]],
    *,
    top_k: int,
    model_path: str | None = None,
    batch_size: int | None = None,
    max_length: int | None = None,
) -> list[tuple[float, ChunkRecord]]:
    # 作用：对混合召回候选做本地精排，并截取最终 top_k 结果。
    if not candidates:
        return []

    resolved_top_k = max(1, top_k)
    resolved_batch_size = batch_size or settings.rag.reranker_batch_size
    resolved_max_length = max_length or settings.rag.reranker_max_length
    reranker = _get_reranker(
        _resolve_model_path(model_path),
        resolved_batch_size,
        resolved_max_length,
    )

    sentence_pairs = [(query, record.text) for _, record in candidates]
    # 这里串行化本地模型打分，避免多线程评测同时切设备导致模型状态异常。
    with _RERANK_LOCK:
        rerank_scores = reranker.compute_score(sentence_pairs)
    if isinstance(rerank_scores, float):
        rerank_scores = [rerank_scores]

    reranked = [
        (float(score), record)
        for score, (_, record) in zip(rerank_scores, candidates)
    ]
    reranked.sort(key=lambda item: item[0], reverse=True)
    return reranked[:resolved_top_k]
