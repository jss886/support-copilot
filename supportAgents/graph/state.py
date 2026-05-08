from typing import Any, Literal, TypedDict


IntentType = Literal["doc_qa", "code_qa", "tool_only", "direct_answer", "fallback"]
ModeType = Literal["auto", "direct", "rag"]
# quality: 检索质量标记，quality_gate 节点写入，answer 节点读取。
# passed=检索有效走RAG，degraded_empty=零结果降级，degraded_low_score=低分降级
QualityType = Literal["passed", "degraded_empty", "degraded_low_score"]
ComplexityType = Literal["simple", "complex"]


class SubTask(TypedDict, total=False):
    """Planner 分解出的单个子任务"""
    sub_query: str
    sub_intent: IntentType
    depends_on: list[int]  # 依赖的子任务索引，空列表表示无依赖
    result: str            # 执行结果，由 execute_subtasks 填充


class PlanPayload(TypedDict, total=False):
    """Planner 输出的完整计划"""
    original_query: str
    sub_tasks: list[SubTask]
    plan_reason: str


class RetrievalItem(TypedDict):
    # 作用：描述单条检索命中的最小结构，方便在 graph 内部传递证据。
    score: float
    source: str
    start: int
    end: int
    text: str
    metadata: dict[str, Any]


class RetrievalPayload(TypedDict, total=False):
    # 作用：承载 retrieval_agent 的输出，既保留原始证据，也保留拼好的上下文文本。
    query: str
    rewritten_queries: list[str]
    items: list[RetrievalItem]
    context_text: str


class ActionPayload(TypedDict, total=False):
    # 作用：记录单次工具调用的输入、输出和状态，action_agent 每轮追加一条。
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: Any
    status: str  # "success" | "error"
    error_message: str


class MemoryPayload(TypedDict, total=False):
    # 作用：承载会话记忆提炼结果，后续可以直接接 sessions 或 task_memory。
    session_summary: str
    user_preferences: dict[str, Any]
    saved: bool


class SupportAgentState(TypedDict, total=False):
    # 作用：定义多 Agent 共享状态，作为 graph 节点之间的统一输入输出协议。
    session_id: str
    user_query: str
    normalized_query: str
    intent: IntentType
    route_reason: str
    messages: list[dict[str, str]]
    retrieval: RetrievalPayload
    action_history: list[ActionPayload]
    action_summary: str
    mode: ModeType
    quality: QualityType
    answer: str
    complexity: ComplexityType
    plan: PlanPayload
    plan_results: list[SubTask]
    synthesized_answer: str
    memory: MemoryPayload
    error: str


# 作用：创建一份最小初始状态，方便 API、CLI 或 graph 入口统一起点。
# mode=auto 走现有路由判断，direct 跳过检索直接回答，rag 强制走检索。
def create_initial_state(
    *,
    user_query: str,
    session_id: str | None = None,
    messages: list[dict[str, str]] | None = None,
    mode: ModeType = "auto",
) -> SupportAgentState:
    state: SupportAgentState = {
        "user_query": user_query,
        "normalized_query": user_query.strip(),
        "mode": mode,
        "messages": messages or [],
    }
    if session_id:
        state["session_id"] = session_id
    return state
