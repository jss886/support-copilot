from typing import Any, Literal, TypedDict


IntentType = Literal["knowledge_qa", "tool_only", "direct_answer", "fallback"]
ModeType = Literal["auto", "direct", "rag"]
# 作用：标记检索质量，便于 answer 节点判断是走 RAG 还是降级回答。
QualityType = Literal["passed", "degraded_empty", "degraded_low_score"]
ComplexityType = Literal["simple", "complex"]
TaskStatusType = Literal["success", "error"]
ReflectionActionType = Literal["finish", "retry", "replan"]
FinalStatusType = Literal["resolved", "degraded", "failed"]


class SubTask(TypedDict, total=False):
    """作用：描述 planner 拆出的单个子任务。"""

    task_id: int
    sub_query: str
    sub_intent: IntentType
    depends_on: list[int]
    result: str


class PlanPayload(TypedDict, total=False):
    """作用：承载 planner 产出的完整计划。"""

    original_query: str
    sub_tasks: list[SubTask]
    plan_reason: str


class TaskEvidence(TypedDict, total=False):
    """作用：描述 worker 返回的一条结构化证据。"""

    kind: str
    source: str
    content: str
    score: float


class TaskExecutionResult(TypedDict, total=False):
    """作用：承载单个子任务的执行结果，供 reflection 和 synthesizer 复用。"""

    task_id: int
    sub_query: str
    sub_intent: IntentType
    depends_on: list[int]
    worker_name: str
    tool_name: str
    status: TaskStatusType
    summary: str
    result: str
    evidence: list[TaskEvidence]
    missing_info: list[str]
    confidence: float
    error: str


class ReflectionPayload(TypedDict, total=False):
    """作用：记录计划执行后的反思结论和下一步动作。"""

    is_solved: bool
    next_action: ReflectionActionType
    reflection_summary: str
    gaps: list[str]
    retryable_task_ids: list[int]
    followup_sub_tasks: list[SubTask]


class RetrievalItem(TypedDict):
    # 作用：描述单条检索命中的最小结果结构，便于 graph 内部传递证据。
    db_chunk_id: str
    score: float
    source: str
    start: int
    end: int
    text: str
    metadata: dict[str, Any]


class RetrievalPayload(TypedDict, total=False):
    # 作用：承载 retrieval_agent 的输出，同时保留原始证据和拼好的上下文文本。
    query: str
    rewritten_queries: list[str]
    hyde_document: str
    raw_item_count: int
    filtered_item_count: int
    items: list[RetrievalItem]
    context_text: str


class ActionPayload(TypedDict, total=False):
    # 作用：记录一次工具调用的输入、输出和状态，action_agent 每轮追加一条。
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: Any
    status: str  # "success" | "error"
    error_message: str


class MemoryPayload(TypedDict, total=False):
    # 作用：承载会话记忆提炼结果，后续可以直接接 session 或 task_memory。
    session_summary: str
    user_preferences: dict[str, Any]
    saved: bool


class SupportAgentState(TypedDict, total=False):
    # 作用：定义多 Agent 共享状态，作为 graph 节点间统一的输入输出协议。
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
    plan_results: list[TaskExecutionResult]
    reflection: ReflectionPayload
    reflection_count: int
    max_reflections: int
    final_status: FinalStatusType
    synthesized_answer: str
    memory: MemoryPayload
    error: str


# 作用：创建一份最小初始状态，方便 API、CLI 和 graph 入口统一起点。
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
        "reflection_count": 0,
        "max_reflections": 2,
        "final_status": "resolved",
    }
    if session_id:
        state["session_id"] = session_id
    return state
