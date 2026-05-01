from fastapi import APIRouter

from api.common import translate_exception
from api.schemas import QueryRequest, RetrievalItem, RetrievalResponse
from rag.retrieval import retrieve

router = APIRouter(prefix="/api/v1/retrieval", tags=["检索"])


# 作用：执行混合检索，并按配置决定是否再做 rerank 精排。
@router.post("/query", response_model=RetrievalResponse, summary="检索相关文本切片")
def query(request: QueryRequest) -> RetrievalResponse:
    try:
        results = retrieve(
            query=request.question,
            top_k=request.top_k,
            source=request.source,
            candidate_top_k=request.candidate_top_k,
            use_rerank=request.use_rerank,
            use_query_rewrite=request.use_query_rewrite,
        )
    except Exception as exc:
        raise translate_exception(exc) from exc

    items = [
        RetrievalItem(
            score=score,
            source=record.source,
            start=record.start,
            end=record.end,
            text=record.text,
            metadata=record.metadata,
        )
        for score, record in results
    ]
    return RetrievalResponse(data=items, message="检索完成。")
