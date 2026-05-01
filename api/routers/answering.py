from fastapi import APIRouter

from api.common import translate_exception
from api.schemas import AnswerRequest, AnswerResponse, AnswerResult
from rag.answering import answer_question

router = APIRouter(prefix="/api/v1/answering", tags=["问答"])


# 作用：执行完整 RAG 问答流程，先检索再基于证据生成答案。
@router.post("/answer", response_model=AnswerResponse, summary="生成问答结果")
def answer(request: AnswerRequest) -> AnswerResponse:
    try:
        result = answer_question(
            question=request.question,
            top_k=request.top_k,
            source=request.source,
            candidate_top_k=request.candidate_top_k,
            use_rerank=request.use_rerank,
            use_query_rewrite=request.use_query_rewrite,
        )
    except Exception as exc:
        raise translate_exception(exc) from exc

    return AnswerResponse(
        data=AnswerResult(answer=result),
        message="问答完成。",
    )
