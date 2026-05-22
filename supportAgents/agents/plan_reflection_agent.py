import json
import logging
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage

from supportAgents.agents.reflection_prompts import PLAN_REFLECTION_SYSTEM_PROMPT
from supportAgents.graph.state import ReflectionPayload, SubTask, SupportAgentState, TaskExecutionResult
from supportAgents.llm_clients import create_llm_client

_RETRY_CONFIDENCE_THRESHOLD = 0.35
logger = logging.getLogger(__name__)


# 作用：构造 reflection 使用的模型实例，专门负责复盘计划执行效果。
def _build_reflection_llm():
    model = os.environ.get("SUPPORT_REFLECTION_MODEL", "deepseek-v4-flash")
    client = create_llm_client("deepseek", model, timeout=30, max_retries=1, temperature=0)
    return client.get_llm()


# 作用：把单个子任务结果压缩成结构化文本，便于 reflection 判断缺口。
def _format_task_result(task_result: TaskExecutionResult) -> str:
    return (
        f"- task_id={task_result.get('task_id', -1)} "
        f"status={task_result.get('status', 'error')} "
        f"confidence={task_result.get('confidence', 0.0):.2f} "
        f"summary={task_result.get('summary', '')} "
        f"missing_info={task_result.get('missing_info', [])} "
        f"error={task_result.get('error', '')}"
    )


# 作用：统计当前执行结果是否还有可用结论，用来区分 degraded 和 failed。
def _has_usable_results(plan_results: list[TaskExecutionResult]) -> bool:
    for result in plan_results:
        if result.get("status") == "success" and (result.get("result") or result.get("summary")):
            return True
    return False


# 作用：把失败轨迹记成结构化日志，便于后续回放和调优 reflection 策略。
def _log_degraded_reflection(state: SupportAgentState, reflection: ReflectionPayload) -> None:
    logger.warning(
        "planner_reflection_degraded: %s",
        json.dumps(
            {
                "session_id": state.get("session_id", ""),
                "user_query": state.get("user_query", ""),
                "reflection_count": state.get("reflection_count", 0),
                "max_reflections": state.get("max_reflections", 2),
                "final_status": state.get("final_status", ""),
                "reflection_summary": reflection.get("reflection_summary", ""),
                "gaps": reflection.get("gaps", []),
                "plan": state.get("plan", {}),
                "plan_results": state.get("plan_results", []),
            },
            ensure_ascii=False,
        ),
    )


# 作用：复用 planner 的子任务协议，保证 reflection 追加的 follow-up tasks 可直接进入执行链路。
def _normalize_followup_sub_tasks(sub_tasks_raw: list[dict]) -> list[SubTask]:
    normalized: list[SubTask] = []
    for raw_task in sub_tasks_raw:
        sub_query = str(raw_task.get("sub_query", "")).strip()
        sub_intent = str(raw_task.get("sub_intent", "knowledge_qa")).strip().lower()
        depends_on = raw_task.get("depends_on", [])
        if not isinstance(depends_on, list):
            depends_on = []
        if not sub_query or sub_intent not in {"knowledge_qa", "tool_only", "direct_answer"}:
            continue
        normalized.append(
            SubTask(
                sub_query=sub_query,
                sub_intent=sub_intent,
                depends_on=[dep for dep in depends_on if isinstance(dep, int)],
                result="",
            )
        )
    return normalized[:3]


# 作用：解析 reflection 输出，避免模型返回散文时破坏 graph 状态。
def _parse_reflection_json(content: str) -> ReflectionPayload | None:
    if not content:
        return None
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    next_action = str(payload.get("next_action", "finish")).strip().lower()
    if next_action not in {"finish", "retry", "replan"}:
        next_action = "finish"
    gaps = payload.get("gaps", [])
    retryable_task_ids = payload.get("retryable_task_ids", [])
    followup_sub_tasks = payload.get("followup_sub_tasks", [])
    return ReflectionPayload(
        is_solved=bool(payload.get("is_solved", next_action == "finish")),
        next_action=next_action,  # type: ignore[typeddict-item]
        reflection_summary=str(payload.get("reflection_summary", "")).strip(),
        gaps=[str(item).strip() for item in gaps if str(item).strip()] if isinstance(gaps, list) else [],
        retryable_task_ids=[
            task_id for task_id in retryable_task_ids if isinstance(task_id, int)
        ]
        if isinstance(retryable_task_ids, list)
        else [],
        followup_sub_tasks=_normalize_followup_sub_tasks(followup_sub_tasks)
        if isinstance(followup_sub_tasks, list)
        else [],
    )


# 作用：在模型不可用时用规则兜底，至少给出可执行的下一步动作。
def _build_fallback_reflection(state: SupportAgentState) -> ReflectionPayload:
    plan_results = state.get("plan_results") or []
    retryable_task_ids: list[int] = []
    gaps: list[str] = []

    for result in plan_results:
        task_id = result.get("task_id")
        status = result.get("status", "error")
        confidence = float(result.get("confidence", 0.0))
        if status == "error" or confidence < _RETRY_CONFIDENCE_THRESHOLD:
            if isinstance(task_id, int):
                retryable_task_ids.append(task_id)
        for item in result.get("missing_info", []):
            if item not in gaps:
                gaps.append(item)

    if retryable_task_ids:
        return ReflectionPayload(
            is_solved=False,
            next_action="retry",
            reflection_summary="存在失败或低置信度子任务，先重试已有任务。",
            gaps=gaps,
            retryable_task_ids=retryable_task_ids,
            followup_sub_tasks=[],
        )
    if gaps:
        return ReflectionPayload(
            is_solved=False,
            next_action="replan",
            reflection_summary="当前计划已有部分结果，但仍存在缺口，建议补充少量 follow-up 子任务。",
            gaps=gaps,
            retryable_task_ids=[],
            followup_sub_tasks=[],
        )
    return ReflectionPayload(
        is_solved=True,
        next_action="finish",
        reflection_summary="当前计划已覆盖主要问题，可进入最终综合。",
        gaps=[],
        retryable_task_ids=[],
        followup_sub_tasks=[],
    )


# 作用：反思达到上限时统一降级收口，并区分还能给部分答案还是彻底失败。
def _build_max_round_reflection(state: SupportAgentState) -> ReflectionPayload:
    plan_results = state.get("plan_results") or []
    gaps: list[str] = []
    for result in plan_results:
        for item in result.get("missing_info", []):
            if item not in gaps:
                gaps.append(item)

    if _has_usable_results(plan_results):
        state["final_status"] = "degraded"
        reflection = ReflectionPayload(
            is_solved=False,
            next_action="finish",
            reflection_summary="已达到最大反思轮次，当前仅输出已确认部分，并明确说明未解决点。",
            gaps=gaps,
            retryable_task_ids=[],
            followup_sub_tasks=[],
        )
    else:
        state["final_status"] = "failed"
        reflection = ReflectionPayload(
            is_solved=False,
            next_action="finish",
            reflection_summary="已达到最大反思轮次，且仍缺少足够有效结果，当前无法给出可靠答案。",
            gaps=gaps,
            retryable_task_ids=[],
            followup_sub_tasks=[],
        )

    _log_degraded_reflection(state, reflection)
    return reflection


# 作用：统一执行计划级反思，决定 finish、retry 还是 replan。
def run_plan_reflection(state: SupportAgentState) -> SupportAgentState:
    next_state: SupportAgentState = dict(state)
    if next_state.get("error"):
        next_state["final_status"] = "failed"
        return next_state

    reflection_count = int(next_state.get("reflection_count", 0))
    max_reflections = int(next_state.get("max_reflections", 2))
    if reflection_count >= max_reflections:
        next_state["reflection"] = _build_max_round_reflection(next_state)
        return next_state

    query = next_state.get("user_query", "")
    plan = next_state.get("plan") or {}
    plan_results = next_state.get("plan_results") or []
    results_text = "\n".join(_format_task_result(result) for result in plan_results) or "无执行结果。"
    plan_text = "\n".join(
        f"- task_id={task.get('task_id', -1)} intent={task.get('sub_intent', '')} query={task.get('sub_query', '')}"
        for task in plan.get("sub_tasks", [])
    ) or "无计划。"

    try:
        llm = _build_reflection_llm()
        response = llm.invoke(
            [
                SystemMessage(content=PLAN_REFLECTION_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"原始问题：{query}\n\n"
                        f"当前计划：\n{plan_text}\n\n"
                        f"计划理由：{plan.get('plan_reason', '')}\n\n"
                        f"执行结果：\n{results_text}"
                    )
                ),
            ]
        )
        reflection = _parse_reflection_json(getattr(response, "content", "") or "")
        if reflection is None:
            reflection = _build_fallback_reflection(next_state)
    except Exception:
        reflection = _build_fallback_reflection(next_state)

    next_state["reflection"] = reflection
    next_state["reflection_count"] = reflection_count + 1
    next_state["final_status"] = "resolved" if reflection.get("next_action") != "finish" or reflection.get("is_solved") else "degraded"
    if reflection.get("is_solved"):
        next_state["final_status"] = "resolved"
    elif reflection.get("next_action") == "finish":
        next_state["final_status"] = "degraded" if _has_usable_results(plan_results) else "failed"
    return next_state
