from fastapi import APIRouter

from api.common import translate_exception
from api.schemas import ChatRequest, ChatResponse, ChatResult, RetrievalItem
from memory import build_session_memory, persist_session_memory
from supportAgents.graph.builder import run_support_graph
from supportAgents.graph.state import create_initial_state

router = APIRouter(prefix="/api/v1/chat", tags=["聊天"])

_ALLOWED_MODES = {"auto", "direct", "rag"}


# 作用：统一处理前端聊天工作台的单轮提问，并返回回答、路由信息和检索证据。
@router.post("/respond", response_model=ChatResponse, summary="生成聊天工作台回答")
def respond(request: ChatRequest) -> ChatResponse:
    normalized_mode = request.mode.strip().lower()
    if normalized_mode not in _ALLOWED_MODES:
        raise translate_exception(ValueError(f"不支持的回答模式：{request.mode}"))

    try:
        state = create_initial_state(
            user_query=request.question,
            session_id=request.session_id,
            messages=request.messages,
            mode=normalized_mode,  # type: ignore[arg-type]
        )
        state = build_session_memory(state)
        result = run_support_graph(state)
        persist_session_memory(result)
    except Exception as exc:
        raise translate_exception(exc) from exc

    retrieval_items = [
        RetrievalItem(
            score=item["score"],
            source=item["source"],
            start=item["start"],
            end=item["end"],
            text=item["text"],
            metadata=item["metadata"],
        )
        for item in (result.get("retrieval") or {}).get("items", [])
    ]
    payload = ChatResult(
        answer=result.get("answer", ""),
        mode=normalized_mode,
        intent=result.get("intent", "fallback"),
        route_reason=result.get("route_reason", ""),
        quality=result.get("quality"),
        retrieval_items=retrieval_items,
    )
    return ChatResponse(data=payload, message="聊天回答生成完成。")
