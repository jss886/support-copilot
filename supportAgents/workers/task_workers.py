from supportAgents.graph.state import (
    SubTask,
    SupportAgentState,
    TaskEvidence,
    TaskExecutionResult,
)
from supportAgents.workers.subgraphs import (
    run_direct_answer_worker_graph,
    run_retrieval_worker_graph,
    run_tool_worker_graph,
)


# 作用：把长文本裁剪到适合汇总和依赖注入的长度，避免子任务结果无限膨胀。
def _clip_text(text: str, limit: int = 240) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "..."


# 作用：基于检索结果抽取结构化证据，后续 supervisor 或 synthesizer 可以直接消费。
def _build_retrieval_evidence(worker_state: SupportAgentState) -> list[TaskEvidence]:
    retrieval = worker_state.get("retrieval") or {}
    items = retrieval.get("items", [])[:3]
    evidence: list[TaskEvidence] = []
    for item in items:
        evidence.append(
            TaskEvidence(
                kind="retrieval",
                source=item.get("source", ""),
                content=_clip_text(item.get("text", ""), limit=180),
                score=float(item.get("score", 0.0)),
            )
        )
    return evidence


# 作用：基于工具调用记录抽取结构化证据，便于后续汇总工具链路的关键信息。
def _build_action_evidence(worker_state: SupportAgentState) -> list[TaskEvidence]:
    action_history = worker_state.get("action_history") or []
    evidence: list[TaskEvidence] = []
    for action in action_history[:5]:
        tool_name = action.get("tool_name", "")
        status = action.get("status", "")
        if status == "success":
            content = _clip_text(str(action.get("tool_output", "")), limit=180)
        else:
            content = _clip_text(str(action.get("error_message", "")), limit=180)
        evidence.append(
            TaskEvidence(
                kind="tool",
                source=tool_name,
                content=content,
                score=1.0 if status == "success" else 0.0,
            )
        )
    return evidence


# 作用：根据 action_history 提炼工具名摘要，方便结果汇总和 trace 展示。
def _summarize_tool_names(worker_state: SupportAgentState) -> str:
    action_history = worker_state.get("action_history") or []
    tool_names: list[str] = []
    for action in action_history:
        tool_name = action.get("tool_name", "")
        if tool_name and tool_name not in tool_names:
            tool_names.append(tool_name)
    return ",".join(tool_names) if tool_names else "action"


# 作用：把统一结构化字段组装成任务执行结果，避免 supervisor 关心底层细节。
def _build_task_result(
    *,
    task_id: int,
    sub_task: SubTask,
    worker_name: str,
    tool_name: str,
    status: str,
    summary: str = "",
    result: str = "",
    evidence: list[TaskEvidence] | None = None,
    missing_info: list[str] | None = None,
    confidence: float = 0.0,
    error: str = "",
) -> TaskExecutionResult:
    return TaskExecutionResult(
        task_id=task_id,
        sub_query=sub_task.get("sub_query", ""),
        sub_intent=sub_task.get("sub_intent", "direct_answer"),
        depends_on=sub_task.get("depends_on", []),
        worker_name=worker_name,
        tool_name=tool_name,
        status=status,
        summary=summary,
        result=result,
        evidence=evidence or [],
        missing_info=missing_info or [],
        confidence=confidence,
        error=error,
    )


# 作用：把 retrieval worker 的状态转换成稳定协议，便于后续切换到 subgraph 时保持输出一致。
def _build_retrieval_result(
    *,
    task_id: int,
    sub_task: SubTask,
    worker_state: SupportAgentState,
    answer: str,
    error: str = "",
) -> TaskExecutionResult:
    quality = worker_state.get("quality", "")
    evidence = _build_retrieval_evidence(worker_state)
    missing_info: list[str] = []
    confidence = 0.8
    if quality == "degraded_empty":
        missing_info.append("知识库未命中与当前子任务直接相关的证据。")
        confidence = 0.25
    elif quality == "degraded_low_score":
        missing_info.append("已命中检索结果，但相关度偏低。")
        confidence = 0.45
    elif not evidence:
        missing_info.append("当前子任务缺少可引用的检索证据。")
        confidence = 0.4

    if error:
        return _build_task_result(
            task_id=task_id,
            sub_task=sub_task,
            worker_name="retrieval_worker",
            tool_name="retrieval",
            status="error",
            summary="检索型子任务执行失败",
            result="",
            evidence=evidence,
            missing_info=missing_info or ["检索链路执行失败。"],
            confidence=0.0,
            error=error,
        )

    summary = _clip_text(answer, limit=140) if answer else "检索型子任务未产出有效回答"
    if not answer:
        missing_info.append("当前子任务没有生成可用回答。")
        confidence = 0.0
    return _build_task_result(
        task_id=task_id,
        sub_task=sub_task,
        worker_name="retrieval_worker",
        tool_name="retrieval",
        status="success" if answer else "error",
        summary=summary,
        result=answer,
        evidence=evidence,
        missing_info=missing_info,
        confidence=confidence,
        error="" if answer else "retrieval_worker_empty_answer",
    )


# 作用：把 tool worker 的状态转换成稳定协议，保留工具证据和缺失信息。
def _build_tool_result(
    *,
    task_id: int,
    sub_task: SubTask,
    worker_state: SupportAgentState,
    answer: str,
    error: str = "",
) -> TaskExecutionResult:
    tool_name = _summarize_tool_names(worker_state)
    evidence = _build_action_evidence(worker_state)
    action_summary = worker_state.get("action_summary", "")
    missing_info: list[str] = []
    success_calls = sum(1 for item in worker_state.get("action_history", []) if item.get("status") == "success")
    confidence = 0.2 if not evidence else min(0.9, 0.35 + success_calls * 0.2)

    if not action_summary and not evidence:
        missing_info.append("工具链路没有返回可用的执行记录。")
        confidence = 0.1
    if error:
        return _build_task_result(
            task_id=task_id,
            sub_task=sub_task,
            worker_name="tool_worker",
            tool_name=tool_name,
            status="error",
            summary="工具型子任务执行失败",
            result="",
            evidence=evidence,
            missing_info=missing_info or ["工具执行链路失败。"],
            confidence=0.0,
            error=error,
        )

    summary_source = action_summary or answer
    summary = _clip_text(summary_source, limit=140) if summary_source else "工具型子任务未产出有效总结"
    if not answer:
        missing_info.append("当前子任务没有生成最终回答。")
        confidence = 0.0
    return _build_task_result(
        task_id=task_id,
        sub_task=sub_task,
        worker_name="tool_worker",
        tool_name=tool_name,
        status="success" if answer else "error",
        summary=summary,
        result=answer,
        evidence=evidence,
        missing_info=missing_info,
        confidence=confidence,
        error="" if answer else "tool_worker_empty_answer",
    )


# 作用：把 direct worker 的状态转换成稳定协议，明确这类任务缺少外部证据支撑。
def _build_direct_result(
    *,
    task_id: int,
    sub_task: SubTask,
    answer: str,
    error: str = "",
) -> TaskExecutionResult:
    if error:
        return _build_task_result(
            task_id=task_id,
            sub_task=sub_task,
            worker_name="direct_answer_worker",
            tool_name="answer",
            status="error",
            summary="直接回答型子任务执行失败",
            result="",
            evidence=[],
            missing_info=["当前子任务未使用外部证据。"],
            confidence=0.0,
            error=error,
        )

    summary = _clip_text(answer, limit=140) if answer else "直接回答型子任务未产出有效回答"
    missing_info = ["当前子任务未使用检索或工具证据。"]
    confidence = 0.45 if answer else 0.0
    return _build_task_result(
        task_id=task_id,
        sub_task=sub_task,
        worker_name="direct_answer_worker",
        tool_name="answer",
        status="success" if answer else "error",
        summary=summary,
        result=answer,
        evidence=[],
        missing_info=missing_info,
        confidence=confidence,
        error="" if answer else "direct_answer_worker_empty_answer",
    )


# 作用：执行 knowledge_qa 子任务，内部仍复用 retrieval -> quality_gate -> answer 链路。
def run_retrieval_worker_task(
    *,
    task_id: int,
    sub_task: SubTask,
    worker_state: SupportAgentState,
) -> TaskExecutionResult:
    try:
        next_state = run_retrieval_worker_graph(worker_state)
        return _build_retrieval_result(
            task_id=task_id,
            sub_task=sub_task,
            worker_state=next_state,
            answer=next_state.get("answer", ""),
        )
    except Exception as exc:
        return _build_retrieval_result(
            task_id=task_id,
            sub_task=sub_task,
            worker_state=worker_state,
            answer="",
            error=str(exc),
        )


# 作用：执行工具型子任务，内部复用 action -> answer 链路。
def run_tool_worker_task(
    *,
    task_id: int,
    sub_task: SubTask,
    worker_state: SupportAgentState,
) -> TaskExecutionResult:
    try:
        next_state = run_tool_worker_graph(worker_state)
        return _build_tool_result(
            task_id=task_id,
            sub_task=sub_task,
            worker_state=next_state,
            answer=next_state.get("answer", ""),
        )
    except Exception as exc:
        return _build_tool_result(
            task_id=task_id,
            sub_task=sub_task,
            worker_state=worker_state,
            answer="",
            error=str(exc),
        )


# 作用：执行直接回答型子任务，适合无需检索和工具的轻量问题。
def run_direct_answer_worker_task(
    *,
    task_id: int,
    sub_task: SubTask,
    worker_state: SupportAgentState,
) -> TaskExecutionResult:
    try:
        next_state = run_direct_answer_worker_graph(worker_state)
        return _build_direct_result(
            task_id=task_id,
            sub_task=sub_task,
            answer=next_state.get("answer", ""),
        )
    except Exception as exc:
        return _build_direct_result(
            task_id=task_id,
            sub_task=sub_task,
            answer="",
            error=str(exc),
        )
