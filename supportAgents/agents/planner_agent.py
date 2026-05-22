import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from langchain_core.messages import HumanMessage, SystemMessage

from memory import load_user_profile_text, retrieve_task_memories
from supportAgents.agents.prompts import PLANNER_SYSTEM_PROMPT
from supportAgents.agents.reflection_prompts import PLANNER_REPLAN_SYSTEM_PROMPT
from supportAgents.graph.state import (
    PlanPayload,
    ReflectionPayload,
    SubTask,
    SupportAgentState,
    TaskExecutionResult,
)
from supportAgents.llm_clients import create_llm_client
from supportAgents.workers.task_workers import (
    run_direct_answer_worker_task,
    run_retrieval_worker_task,
    run_tool_worker_task,
)

_VALID_SUB_INTENTS = {"knowledge_qa", "tool_only", "direct_answer"}
_RETRY_CONFIDENCE_THRESHOLD = 0.35


# 作用：把最近原始对话整理成紧凑文本，保留当前会话的最新上下文。
def _format_recent_messages(messages: list[dict[str, str]]) -> str:
    if not messages:
        return "无最近对话。"
    lines: list[str] = []
    for message in messages:
        role = message.get("role", "user")
        content = (message.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


# 作用：在 planner 前拼接短期记忆、用户画像和 task_memory，避免重复规划已知路径。
def _build_planner_memory_block(state: SupportAgentState) -> str:
    session_memory = (state.get("session_memory") or {}).get("summary", {})
    recent_messages = state.get("recent_messages") or state.get("messages", [])
    try:
        user_profile_text = load_user_profile_text(state.get("user_id", ""))
    except Exception:
        user_profile_text = ""
    try:
        task_memory_text = retrieve_task_memories(state.get("user_query", ""))
    except Exception:
        task_memory_text = ""

    blocks = [
        "当前 SessionSummary：",
        f"- summary: {session_memory.get('summary', '')}",
        f"- current_goal: {session_memory.get('current_goal', '')}",
        f"- key_facts: {session_memory.get('key_facts', [])}",
        f"- open_issues: {session_memory.get('open_issues', [])}",
        f"- failed_attempts: {session_memory.get('failed_attempts', [])}",
        "",
        "最近 20 轮原始对话：",
        _format_recent_messages(recent_messages),
    ]
    if user_profile_text:
        blocks.extend(["", user_profile_text])
    if task_memory_text:
        blocks.extend(["", task_memory_text])
    return "\n".join(blocks)


# 作用：构造 planner 使用的模型实例，保持任务拆解输出稳定。
def _build_planner_llm():
    model = os.environ.get("SUPPORT_PLANNER_MODEL", "deepseek-v4-flash")
    client = create_llm_client("deepseek", model, timeout=30, max_retries=1, temperature=0)
    return client.get_llm()


# 作用：把原始子任务列表整理成带 task_id 的规范结构。
def _normalize_sub_tasks(
    sub_tasks_raw: list[dict],
    *,
    task_id_offset: int = 0,
    valid_dependency_ids: set[int] | None = None,
) -> list[SubTask]:
    sub_tasks: list[SubTask] = []
    valid_task_ids: set[int] = set(valid_dependency_ids or set())

    for raw_index, raw_task in enumerate(sub_tasks_raw):
        sub_query = str(raw_task.get("sub_query", "")).strip()
        sub_intent = str(raw_task.get("sub_intent", "knowledge_qa")).strip().lower()
        depends_on_raw = raw_task.get("depends_on", [])
        if not isinstance(depends_on_raw, list):
            depends_on_raw = []

        if not sub_query or sub_intent not in _VALID_SUB_INTENTS:
            continue

        task_id = task_id_offset + raw_index
        allowed_local_ids = {task_id_offset + idx for idx in range(raw_index)}
        depends_on = [
            dep_id
            for dep_id in depends_on_raw
            if isinstance(dep_id, int) and dep_id in valid_task_ids.union(allowed_local_ids)
        ]
        valid_task_ids.add(task_id)
        sub_tasks.append(
            SubTask(
                task_id=task_id,
                sub_query=sub_query,
                sub_intent=sub_intent,
                depends_on=depends_on,
                result="",
            )
        )

    return sub_tasks


# 作用：解析 planner 的 JSON 输出；解析失败时返回 None。
def _parse_plan_json(
    content: str,
    *,
    task_id_offset: int = 0,
    valid_dependency_ids: set[int] | None = None,
) -> PlanPayload | None:
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

    sub_tasks_raw = payload.get("sub_tasks", [])
    if not isinstance(sub_tasks_raw, list) or not sub_tasks_raw:
        return None

    sub_tasks = _normalize_sub_tasks(
        sub_tasks_raw,
        task_id_offset=task_id_offset,
        valid_dependency_ids=valid_dependency_ids,
    )
    if not sub_tasks:
        return None

    plan_reason = str(payload.get("plan_reason", "")).strip()
    return PlanPayload(
        original_query="",
        sub_tasks=sub_tasks,
        plan_reason=plan_reason,
    )


# 作用：把任务列表转成稳定摘要，便于 replan 时告知模型旧计划做过什么。
def _format_plan_summary(sub_tasks: list[SubTask]) -> str:
    if not sub_tasks:
        return "无历史计划。"
    lines: list[str] = []
    for task in sub_tasks:
        lines.append(
            f"- task_id={task.get('task_id', -1)} "
            f"intent={task.get('sub_intent', '')} "
            f"depends_on={task.get('depends_on', [])} "
            f"query={task.get('sub_query', '')}"
        )
    return "\n".join(lines)


# 作用：把执行结果压缩成文本，供 replan 判断哪些任务已完成、哪些仍有缺口。
def _format_plan_results_summary(plan_results: list[TaskExecutionResult]) -> str:
    if not plan_results:
        return "无历史执行结果。"
    lines: list[str] = []
    for result in plan_results:
        lines.append(
            f"- task_id={result.get('task_id', -1)} "
            f"status={result.get('status', 'error')} "
            f"confidence={result.get('confidence', 0.0):.2f} "
            f"summary={result.get('summary', '')} "
            f"missing={result.get('missing_info', [])} "
            f"error={result.get('error', '')}"
        )
    return "\n".join(lines)


# 作用：把 reflection 指出的 follow-up 子任务追加到旧计划末尾，而不是整份重写。
def _append_followup_sub_tasks(
    plan: PlanPayload,
    followup_sub_tasks: list[SubTask],
) -> PlanPayload:
    existing_sub_tasks = list(plan.get("sub_tasks", []))
    next_task_id = max((task.get("task_id", -1) for task in existing_sub_tasks), default=-1) + 1
    valid_dependency_ids = {task.get("task_id", -1) for task in existing_sub_tasks if isinstance(task.get("task_id"), int)}

    normalized_followups = _normalize_sub_tasks(
        [dict(task) for task in followup_sub_tasks],
        task_id_offset=next_task_id,
        valid_dependency_ids=valid_dependency_ids,
    )
    if not normalized_followups:
        return plan

    merged_plan: PlanPayload = dict(plan)
    merged_plan["sub_tasks"] = existing_sub_tasks + normalized_followups
    return merged_plan


# 作用：根据 reflection 结果构造补规划提示，避免 planner 从零推翻旧计划。
def _build_replan_user_prompt(state: SupportAgentState) -> str:
    query = state.get("user_query", "")
    plan = state.get("plan") or {}
    sub_tasks = plan.get("sub_tasks", [])
    plan_results = state.get("plan_results") or []
    reflection = state.get("reflection") or {}
    gaps = reflection.get("gaps", [])

    return (
        f"原始问题：{query}\n\n"
        f"{_build_planner_memory_block(state)}\n\n"
        f"已有计划：\n{_format_plan_summary(sub_tasks)}\n\n"
        f"执行结果：\n{_format_plan_results_summary(plan_results)}\n\n"
        f"反思摘要：{reflection.get('reflection_summary', '')}\n"
        f"待补足缺口：{gaps}\n\n"
        "请只补充新的子任务，不要重复已经成功完成的任务。"
    )


# 作用：根据当前状态判断是否进入 replan 分支。
def _should_replan(state: SupportAgentState) -> bool:
    reflection = state.get("reflection") or {}
    return reflection.get("next_action") == "replan"


# 作用：根据 reflection 选择重试任务，优先重跑明确失败或低置信度任务。
def _select_retry_task_ids(
    sub_tasks: list[SubTask],
    existing_results: dict[int, TaskExecutionResult],
    reflection: ReflectionPayload,
) -> set[int]:
    requested_ids = {
        task_id
        for task_id in reflection.get("retryable_task_ids", [])
        if isinstance(task_id, int)
    }
    if requested_ids:
        return requested_ids

    retry_ids: set[int] = set()
    for task in sub_tasks:
        task_id = task.get("task_id")
        if not isinstance(task_id, int):
            continue
        result = existing_results.get(task_id)
        if not result:
            retry_ids.add(task_id)
            continue
        if result.get("status") == "error" or float(result.get("confidence", 0.0)) < _RETRY_CONFIDENCE_THRESHOLD:
            retry_ids.add(task_id)
    return retry_ids


# 作用：在增量执行时补齐依赖任务，避免被重跑任务缺少上游输入。
def _expand_with_dependencies(task_ids: set[int], task_map: dict[int, SubTask]) -> set[int]:
    expanded = set(task_ids)
    queue = list(task_ids)
    while queue:
        task_id = queue.pop()
        task = task_map.get(task_id)
        if not task:
            continue
        for dep_id in task.get("depends_on", []):
            if dep_id not in expanded:
                expanded.add(dep_id)
                queue.append(dep_id)
    return expanded


# 作用：确定当前这一轮真正要执行哪些任务，支持首次执行、retry 和 replan 增量执行。
def _resolve_tasks_to_execute(
    state: SupportAgentState,
    sub_tasks: list[SubTask],
    existing_results: dict[int, TaskExecutionResult],
) -> set[int]:
    reflection = state.get("reflection") or {}
    task_map = _build_task_map(sub_tasks)
    action = reflection.get("next_action")

    if action == "retry":
        return _expand_with_dependencies(_select_retry_task_ids(sub_tasks, existing_results, reflection), task_map)

    if action == "replan":
        return {
            task_id
            for task_id in task_map
            if task_id not in existing_results
        }

    return set(task_map)


# 作用：把 planner 的复杂用户问题拆成有序子任务列表，或在 replan 时补充任务。
def run_planner(state: SupportAgentState) -> SupportAgentState:
    next_state: SupportAgentState = dict(state)
    if next_state.get("error"):
        return next_state

    query = next_state.get("user_query", "")
    intent = next_state.get("intent", "knowledge_qa")
    reflection = next_state.get("reflection") or {}

    # 作用：如果 reflection 已经给出了 follow-up 子任务，优先直接追加，避免再次让模型发散。
    if _should_replan(next_state):
        followup_sub_tasks = reflection.get("followup_sub_tasks", [])
        if followup_sub_tasks:
            existing_plan = dict(next_state.get("plan") or PlanPayload(original_query=query, sub_tasks=[], plan_reason=""))
            merged_plan = _append_followup_sub_tasks(existing_plan, followup_sub_tasks)
            merged_plan["original_query"] = query
            if not merged_plan.get("plan_reason"):
                merged_plan["plan_reason"] = "基于 reflection 追加 follow-up 子任务。"
            next_state["plan"] = merged_plan
            return next_state

    llm = _build_planner_llm()
    try:
        system_prompt = PLANNER_REPLAN_SYSTEM_PROMPT if _should_replan(next_state) else PLANNER_SYSTEM_PROMPT
        user_prompt = (
            _build_replan_user_prompt(next_state)
            if _should_replan(next_state)
            else (
                f"用户问题：{query}\n"
                f"整体意图：{intent}\n\n"
                f"{_build_planner_memory_block(next_state)}\n\n"
                "请结合以上记忆拆解为子任务，避免重复已经确认或已经失败的路径。"
            )
        )
        task_id_offset = len((next_state.get("plan") or {}).get("sub_tasks", [])) if _should_replan(next_state) else 0
        valid_dependency_ids = {
            task.get("task_id", -1)
            for task in (next_state.get("plan") or {}).get("sub_tasks", [])
            if isinstance(task.get("task_id"), int)
        }
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        plan = _parse_plan_json(
            getattr(response, "content", "") or "",
            task_id_offset=task_id_offset,
            valid_dependency_ids=valid_dependency_ids,
        )
        if plan is not None:
            if _should_replan(next_state):
                existing_plan = dict(next_state.get("plan") or {})
                existing_sub_tasks = list(existing_plan.get("sub_tasks", []))
                plan["sub_tasks"] = existing_sub_tasks + list(plan.get("sub_tasks", []))
                if existing_plan.get("plan_reason"):
                    plan["plan_reason"] = (
                        f"{existing_plan['plan_reason']}\n补规划：{plan.get('plan_reason', '')}".strip()
                    )
            plan["original_query"] = query
            next_state["plan"] = plan
            return next_state
    except Exception:
        pass

    # 作用：replan 失败时保留旧计划，避免把已执行结果整份冲掉。
    if _should_replan(next_state) and next_state.get("plan"):
        return next_state

    # 作用：planner 失败时降级成单子任务，避免复杂链路直接中断。
    next_state["plan"] = PlanPayload(
        original_query=query,
        sub_tasks=[
            SubTask(
                task_id=0,
                sub_query=query,
                sub_intent=intent,
                depends_on=[],
                result="",
            )
        ],
        plan_reason="fallback: planner 解析失败，原问题作为单一子任务。",
    )
    return next_state


# 作用：构建 task_id 到子任务的映射，避免后续调度依赖列表位置。
def _build_task_map(sub_tasks: list[SubTask]) -> dict[int, SubTask]:
    return {
        task["task_id"]: task
        for task in sub_tasks
        if isinstance(task.get("task_id"), int)
    }


# 作用：按 DAG 依赖分波次，同一波次内的任务互不依赖，可以并发执行。
def _topological_waves(sub_tasks: list[SubTask]) -> list[list[int]] | None:
    task_map = _build_task_map(sub_tasks)
    in_degree = {task_id: 0 for task_id in task_map}
    adjacency = {task_id: [] for task_id in task_map}

    for task_id, task in task_map.items():
        for dep_id in task.get("depends_on", []):
            if dep_id not in task_map:
                continue
            adjacency[dep_id].append(task_id)
            in_degree[task_id] += 1

    remaining = set(task_map)
    waves: list[list[int]] = []

    while remaining:
        wave = sorted(task_id for task_id in remaining if in_degree[task_id] == 0)
        if not wave:
            return None
        waves.append(wave)
        for task_id in wave:
            remaining.remove(task_id)
            for neighbor in adjacency[task_id]:
                in_degree[neighbor] -= 1

    return waves


# 作用：把前置子任务结果注入当前任务输入，让 worker 能复用已完成结论。
def _build_worker_query(
    *,
    sub_task: SubTask,
    execution_results: dict[int, TaskExecutionResult],
) -> str:
    sub_query = sub_task.get("sub_query", "")
    dependency_blocks: list[str] = []
    for dep_id in sub_task.get("depends_on", []):
        dep_result = execution_results.get(dep_id)
        if not dep_result:
            continue

        dep_text = dep_result.get("summary", "") or dep_result.get("result", "")
        dep_error = dep_result.get("error", "")
        if dep_text:
            dependency_blocks.append(f"[前置任务 {dep_id}] {dep_text}")
        elif dep_error:
            dependency_blocks.append(f"[前置任务 {dep_id} 失败] {dep_error}")

    if not dependency_blocks:
        return sub_query
    return "\n".join(dependency_blocks) + f"\n当前子问题：{sub_query}"


# 作用：构造 worker 输入状态，便于后续替换成更完整的 subgraph。
def _build_worker_state(
    *,
    parent_state: SupportAgentState,
    sub_task: SubTask,
    execution_results: dict[int, TaskExecutionResult],
) -> SupportAgentState:
    task_id = sub_task.get("task_id", -1)
    worker_query = _build_worker_query(
        sub_task=sub_task,
        execution_results=execution_results,
    )
    return SupportAgentState(
        session_id=parent_state.get("session_id", ""),
        user_query=worker_query,
        normalized_query=worker_query.strip(),
        intent=sub_task.get("sub_intent", "direct_answer"),
        route_reason=f"planner_supervisor_task_{task_id}",
        messages=parent_state.get("messages", []),
        mode="auto",
    )


# 作用：根据子任务意图选择合适 worker，并统一走函数接口。
def _dispatch_worker(
    *,
    sub_task: SubTask,
    worker_state: SupportAgentState,
) -> TaskExecutionResult:
    task_id = sub_task.get("task_id", -1)
    sub_intent = sub_task.get("sub_intent", "direct_answer")
    if sub_intent == "knowledge_qa":
        return run_retrieval_worker_task(
            task_id=task_id,
            sub_task=sub_task,
            worker_state=worker_state,
        )
    if sub_intent == "tool_only":
        return run_tool_worker_task(
            task_id=task_id,
            sub_task=sub_task,
            worker_state=worker_state,
        )
    return run_direct_answer_worker_task(
        task_id=task_id,
        sub_task=sub_task,
        worker_state=worker_state,
    )


# 作用：执行单个子任务，作为并发调度时的最小执行单元。
def _execute_single_task(
    *,
    parent_state: SupportAgentState,
    sub_task: SubTask,
    execution_results: dict[int, TaskExecutionResult],
) -> TaskExecutionResult:
    worker_state = _build_worker_state(
        parent_state=parent_state,
        sub_task=sub_task,
        execution_results=execution_results,
    )
    return _dispatch_worker(sub_task=sub_task, worker_state=worker_state)


# 作用：按 supervisor 方式调度子任务，支持 retry 和 replan 的增量执行。
def run_execute_subtasks(state: SupportAgentState) -> SupportAgentState:
    next_state: SupportAgentState = dict(state)
    if next_state.get("error"):
        return next_state

    plan = next_state.get("plan") or {}
    sub_tasks = plan.get("sub_tasks", [])
    if not sub_tasks:
        next_state["plan_results"] = []
        return next_state

    task_map = _build_task_map(sub_tasks)
    waves = _topological_waves(sub_tasks)
    if waves is None:
        next_state["error"] = "planner_cycle_detected"
        return next_state

    existing_results_list = next_state.get("plan_results") or []
    execution_results: dict[int, TaskExecutionResult] = {
        result["task_id"]: result
        for result in existing_results_list
        if isinstance(result.get("task_id"), int)
    }
    tasks_to_execute = _resolve_tasks_to_execute(next_state, sub_tasks, execution_results)
    max_workers = int(os.environ.get("PLANNER_MAX_WORKERS", "0")) or None

    for wave in waves:
        runnable_wave = [task_id for task_id in wave if task_id in tasks_to_execute]
        if not runnable_wave:
            continue

        if len(runnable_wave) == 1:
            task_id = runnable_wave[0]
            task_result = _execute_single_task(
                parent_state=next_state,
                sub_task=task_map[task_id],
                execution_results=execution_results,
            )
            execution_results[task_id] = task_result
            continue

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task_id = {
                executor.submit(
                    _execute_single_task,
                    parent_state=next_state,
                    sub_task=task_map[task_id],
                    execution_results=dict(execution_results),
                ): task_id
                for task_id in runnable_wave
            }

            wave_results: dict[int, TaskExecutionResult] = {}
            for future, task_id in future_to_task_id.items():
                wave_results[task_id] = future.result()

        for task_id in runnable_wave:
            execution_results[task_id] = wave_results[task_id]

    ordered_results = [
        execution_results[task_id]
        for task_id in sorted(execution_results)
        if task_id in execution_results
    ]
    next_state["plan_results"] = ordered_results
    return next_state
