import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from langchain_core.messages import HumanMessage, SystemMessage

from supportAgents.agents.prompts import PLANNER_SYSTEM_PROMPT
from supportAgents.graph.state import (
    PlanPayload,
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


# 作用：构造 planner 专用模型实例，保持复杂任务分解成本可控。
def _build_planner_llm():
    model = os.environ.get("SUPPORT_PLANNER_MODEL", "deepseek-v4-flash")
    client = create_llm_client("deepseek", model, timeout=30, max_retries=1, temperature=0)
    return client.get_llm()


# 作用：把 planner 原始输出整理成带 task_id 的规范子任务。
def _normalize_sub_tasks(sub_tasks_raw: list[dict]) -> list[SubTask]:
    sub_tasks: list[SubTask] = []
    valid_task_ids: set[int] = set()

    for raw_index, raw_task in enumerate(sub_tasks_raw):
        sub_query = str(raw_task.get("sub_query", "")).strip()
        sub_intent = str(raw_task.get("sub_intent", "knowledge_qa")).strip().lower()
        depends_on_raw = raw_task.get("depends_on", [])
        if not isinstance(depends_on_raw, list):
            depends_on_raw = []

        if not sub_query or sub_intent not in _VALID_SUB_INTENTS:
            continue

        # 这里让 depends_on 依赖稳定的 task_id，而不是最终列表位置。
        depends_on = [
            dep_id
            for dep_id in depends_on_raw
            if isinstance(dep_id, int) and dep_id < raw_index and dep_id in valid_task_ids
        ]
        task_id = raw_index
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


# 作用：把 planner 的 JSON 输出解析成结构化计划，解析失败时返回 None。
def _parse_plan_json(content: str) -> PlanPayload | None:
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

    sub_tasks = _normalize_sub_tasks(sub_tasks_raw)
    if not sub_tasks:
        return None

    plan_reason = str(payload.get("plan_reason", "")).strip()
    return PlanPayload(
        original_query="",
        sub_tasks=sub_tasks,
        plan_reason=plan_reason,
    )


# 作用：将复杂用户问题分解为有序子任务列表，写入 state["plan"]。
def run_planner(state: SupportAgentState) -> SupportAgentState:
    next_state: SupportAgentState = dict(state)
    if next_state.get("error"):
        return next_state

    query = next_state.get("user_query", "")
    intent = next_state.get("intent", "knowledge_qa")

    llm = _build_planner_llm()
    try:
        response = llm.invoke(
            [
                SystemMessage(content=PLANNER_SYSTEM_PROMPT),
                HumanMessage(
                    content=f"用户问题：{query}\n整体意图：{intent}\n请将以上问题分解为子任务。"
                ),
            ]
        )
        plan = _parse_plan_json(getattr(response, "content", "") or "")
        if plan is not None:
            plan["original_query"] = query
            next_state["plan"] = plan
            return next_state
    except Exception:
        pass

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
        plan_reason="fallback: planner 解析失败，原问题作为单一子任务",
    )
    return next_state


# 作用：构建 task_id 到子任务的映射，避免后续调度依赖列表位置。
def _build_task_map(sub_tasks: list[SubTask]) -> dict[int, SubTask]:
    return {
        task["task_id"]: task
        for task in sub_tasks
        if isinstance(task.get("task_id"), int)
    }


# 作用：按 task_id 计算拓扑顺序；如果存在循环依赖则返回 None。
def _topological_order(sub_tasks: list[SubTask]) -> list[int] | None:
    task_map = _build_task_map(sub_tasks)
    in_degree = {task_id: 0 for task_id in task_map}
    adjacency = {task_id: [] for task_id in task_map}

    for task_id, task in task_map.items():
        for dep_id in task.get("depends_on", []):
            if dep_id not in task_map:
                continue
            adjacency[dep_id].append(task_id)
            in_degree[task_id] += 1

    ready = sorted(task_id for task_id, degree in in_degree.items() if degree == 0)
    order: list[int] = []
    while ready:
        task_id = ready.pop(0)
        order.append(task_id)
        for neighbor in adjacency[task_id]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                ready.append(neighbor)
                ready.sort()

    return order if len(order) == len(task_map) else None


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


# 作用：把前置子任务结果注入当前任务输入，先用文本协议保持 supervisor 与 worker 解耦。
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


# 作用：构造 worker 输入状态，后续替换成 subgraph 时可以继续复用这层协议。
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


# 作用：按子任务意图选择合适 worker，先统一走函数接口，后续可平滑替换成 subgraph。
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


# 作用：以 supervisor 方式调度子任务，按依赖波次并发执行同一层内的无依赖子任务。
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

    execution_results: dict[int, TaskExecutionResult] = {}
    ordered_results: list[TaskExecutionResult] = []
    max_workers = int(os.environ.get("PLANNER_MAX_WORKERS", "0")) or None

    for wave in waves:
        if len(wave) == 1:
            task_id = wave[0]
            task_result = _execute_single_task(
                parent_state=next_state,
                sub_task=task_map[task_id],
                execution_results=execution_results,
            )
            execution_results[task_id] = task_result
            ordered_results.append(task_result)
            continue

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task_id = {
                executor.submit(
                    _execute_single_task,
                    parent_state=next_state,
                    sub_task=task_map[task_id],
                    execution_results=dict(execution_results),
                ): task_id
                for task_id in wave
            }

            wave_results: dict[int, TaskExecutionResult] = {}
            for future, task_id in future_to_task_id.items():
                wave_results[task_id] = future.result()

        for task_id in wave:
            execution_results[task_id] = wave_results[task_id]
            ordered_results.append(wave_results[task_id])

    next_state["plan_results"] = ordered_results
    return next_state
