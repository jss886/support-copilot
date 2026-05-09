from pathlib import Path
from threading import Lock
from typing import Any

import requests

from rag.config import PROJECT_ROOT, settings
from rag.models import ChunkRecord

_RERANK_LOCK = Lock()
_RERANKER_CACHE: dict[tuple[str, int, int], Any] = {}


# 作用：统一解析本地 reranker 模型路径，兼容相对路径和配置默认值。
def _resolve_model_path(model_path: str | None) -> str:
    resolved_path = Path(model_path or settings.rag.reranker_model_path)
    if not resolved_path.is_absolute():
        resolved_path = PROJECT_ROOT / resolved_path
    if not resolved_path.exists():
        raise ValueError(f"Reranker model path does not exist: {resolved_path}")
    return str(resolved_path)


# 作用：按模型配置缓存本地 reranker 实例，避免重复加载大模型。
def _get_local_reranker(
    model_path: str,
    batch_size: int,
    max_length: int,
) -> Any:
    cache_key = (model_path, batch_size, max_length)
    with _RERANK_LOCK:
        reranker = _RERANKER_CACHE.get(cache_key)
        if reranker is None:
            from FlagEmbedding import FlagReranker

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


# 作用：调用本地 reranker 做精排，适合离线评测或无外部 API 场景。
def _rerank_with_local_model(
    query: str,
    candidates: list[tuple[float, ChunkRecord]],
    *,
    top_k: int,
    model_path: str | None = None,
    batch_size: int | None = None,
    max_length: int | None = None,
) -> list[tuple[float, ChunkRecord]]:
    if not candidates:
        return []

    resolved_top_k = max(1, top_k)
    resolved_batch_size = batch_size or settings.rag.reranker_batch_size
    resolved_max_length = max_length or settings.rag.reranker_max_length
    reranker = _get_local_reranker(
        _resolve_model_path(model_path),
        resolved_batch_size,
        resolved_max_length,
    )

    sentence_pairs = [(query, record.text) for _, record in candidates]
    # 这里串行化本地模型打分，避免多线程同时访问 CPU 模型导致状态不稳定。
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


# 作用：把 DashScope 重排结果统一转换成 index->score 映射，兼容不同返回结构。
def _extract_dashscope_scores(payload: dict[str, Any]) -> dict[int, float]:
    results = payload.get("results")
    if results is None:
        results = payload.get("output", {}).get("results", [])

    score_by_index: dict[int, float] = {}
    for item in results:
        index = item.get("index")
        score = item.get("relevance_score")
        if index is None or score is None:
            continue
        score_by_index[int(index)] = float(score)
    return score_by_index


# 作用：调用 DashScope 文本重排 API，用托管服务替代本地 CPU 精排。
def _rerank_with_dashscope_api(
    query: str,
    candidates: list[tuple[float, ChunkRecord]],
    *,
    top_k: int,
    api_key: str | None = None,
    model: str | None = None,
    api_url: str | None = None,
    timeout: int | None = None,
) -> list[tuple[float, ChunkRecord]]:
    if not candidates:
        return []

    resolved_api_key = api_key or settings.dashscope.api_key
    if not resolved_api_key:
        raise ValueError("Missing DASHSCOPE_API_KEY for dashscope_api rerank mode.")

    resolved_top_k = max(1, min(top_k, len(candidates)))
    resolved_model = model or settings.rag.rerank_model
    resolved_api_url = api_url or settings.rag.rerank_api_url
    resolved_timeout = timeout or settings.rag.rerank_timeout

    response = requests.post(
        resolved_api_url,
        headers={
            "Authorization": f"Bearer {resolved_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": resolved_model,
            "input": {
                "query": query,
                "documents": [record.text for _, record in candidates],
            },
            "parameters": {
                "top_n": resolved_top_k,
                "return_documents": False,
            },
        },
        timeout=resolved_timeout,
    )
    response.raise_for_status()
    score_by_index = _extract_dashscope_scores(response.json())

    reranked = [
        (score, candidates[index][1])
        for index, score in score_by_index.items()
        if 0 <= index < len(candidates)
    ]
    reranked.sort(key=lambda item: item[0], reverse=True)

    # 如果远端返回异常缺项，则保底补上原候选，避免整条检索链路直接空掉。
    if len(reranked) < resolved_top_k:
        seen_keys = {record.db_chunk_id or record.chunk_id for _, record in reranked}
        for original_score, record in candidates:
            record_key = record.db_chunk_id or record.chunk_id
            if record_key in seen_keys:
                continue
            reranked.append((float(original_score), record))
            seen_keys.add(record_key)
            if len(reranked) >= resolved_top_k:
                break

    return reranked[:resolved_top_k]


# 作用：根据配置选择 disabled/local/dashscope_api 三种重排模式。
def rerank_chunks(
    query: str,
    candidates: list[tuple[float, ChunkRecord]],
    *,
    top_k: int,
    model_path: str | None = None,
    batch_size: int | None = None,
    max_length: int | None = None,
    mode: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    api_url: str | None = None,
    timeout: int | None = None,
) -> list[tuple[float, ChunkRecord]]:
    resolved_mode = (mode or settings.rag.rerank_mode).lower()
    if not candidates:
        return []
    if resolved_mode == "disabled":
        return candidates[: max(1, top_k)]
    if resolved_mode == "local":
        return _rerank_with_local_model(
            query,
            candidates,
            top_k=top_k,
            model_path=model_path,
            batch_size=batch_size,
            max_length=max_length,
        )
    if resolved_mode == "dashscope_api":
        return _rerank_with_dashscope_api(
            query,
            candidates,
            top_k=top_k,
            api_key=api_key,
            model=model,
            api_url=api_url,
            timeout=timeout,
        )
    raise ValueError(f"Unsupported rerank mode: {resolved_mode}")
