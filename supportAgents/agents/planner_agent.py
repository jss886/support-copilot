import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage

from supportAgents.agents.prompts import PLANNER_SYSTEM_PROMPT
from supportAgents.graph.state import PlanPayload, SubTask, SupportAgentState
from supportAgents.llm_clients import create_llm_client

_VALID_SUB_INTENTS = {"doc_qa", "code_qa", "tool_only", "direct_answer"}


def _build_planner_llm():
    model = os.environ.get("SUPPORT_PLANNER_MODEL", "deepseek-v4-flash")
    client = create_llm_client("deepseek", model, timeout=30, max_retries=1, temperature=0)
    return client.get_llm()


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

    sub_tasks: list[SubTask] = []
    for i, st in enumerate(sub_tasks_raw):
        sub_query = st.get("sub_query", "").strip()
        sub_intent = st.get("sub_intent", "doc_qa").strip().lower()
        depends_on = st.get("depends_on", [])
        if not isinstance(depends_on, list):
            depends_on = []
        # 校验 depends_on 索引范围
        depends_on = [d for d in depends_on if isinstance(d, int) and 0 <= d < i]
        if not sub_query or sub_intent not in _VALID_SUB_INTENTS:
            continue
        sub_tasks.append(
            SubTask(
                sub_query=sub_query,
                sub_intent=sub_intent,
                depends_on=depends_on,
                result="",
            )
        )

    if not sub_tasks:
        return None

    plan_reason = payload.get("plan_reason", "").strip()
    return PlanPayload(
        original_query="",
        sub_tasks=sub_tasks,
        plan_reason=plan_reason,
    )


def run_planner(state: SupportAgentState) -> SupportAgentState:
    """将复杂用户问题分解为有序子任务列表，写入 state["plan"]."""
    next_state: SupportAgentState = dict(state)
    if next_state.get("error"):
        return next_state

    query = next_state.get("user_query", "")
    intent = next_state.get("intent", "doc_qa")

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

    # 分解失败，降级为直接处理原问题
    next_state["plan"] = PlanPayload(
        original_query=query,
        sub_tasks=[
            SubTask(
                sub_query=query,
                sub_intent=intent,
                depends_on=[],
                result="",
            )
        ],
        plan_reason="fallback: planner 解析失败，原问题作为单一子任务",
    )
    return next_state


def _topological_order(sub_tasks: list[SubTask]) -> list[int] | None:
    """返回子任务的拓扑排序索引列表，存在环则返回 None."""
    n = len(sub_tasks)
    in_degree = [0] * n
    adj: list[list[int]] = [[] for _ in range(n)]

    for i, st in enumerate(sub_tasks):
        for dep in st.get("depends_on", []):
            if isinstance(dep, int) and 0 <= dep < n:
                adj[dep].append(i)
                in_degree[i] += 1

    queue = [i for i in range(n) if in_degree[i] == 0]
    order: list[int] = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return order if len(order) == n else None


def run_execute_subtasks(state: SupportAgentState) -> SupportAgentState:
    """按拓扑序逐个执行子任务，复用现有 agent 函数。结果写入 plan_results."""
    from supportAgents.agents.answer_agent import run_answer_agent
    from supportAgents.agents.orchestrator_agent import run_orchestrator
    from supportAgents.agents.quality_gate import run_quality_gate
    from supportAgents.agents.retrieval_agent import run_retrieval_agent

    next_state: SupportAgentState = dict(state)
    if next_state.get("error"):
        return next_state

    plan = next_state.get("plan") or {}
    sub_tasks = plan.get("sub_tasks", [])

    if not sub_tasks:
        next_state["plan_results"] = []
        return next_state

    order = _topological_order(sub_tasks)
    if order is None:
        next_state["error"] = "planner_cycle_detected"
        return next_state

    executed: list[SubTask] = [dict(st) for st in sub_tasks]

    for idx in order:
        st = executed[idx]
        sub_query = st.get("sub_query", "")
        sub_intent = st.get("sub_intent", "doc_qa")
        depends_on = st.get("depends_on", [])

        # 将依赖子任务的结果注入查询上下文
        dep_results = []
        for dep_idx in depends_on:
            if 0 <= dep_idx < len(executed):
                dep_result = executed[dep_idx].get("result", "")
                if dep_result:
                    dep_results.append(f"[前置信息 {dep_idx}] {dep_result}")
        if dep_results:
            sub_query = "\n".join(dep_results) + f"\n当前子问题：{sub_query}"

        # 构造 mini state，复用现有节点
        mini_state: SupportAgentState = {
            "session_id": next_state.get("session_id", ""),
            "user_query": sub_query,
            "normalized_query": sub_query.strip(),
            "intent": sub_intent,
            "route_reason": f"planner_subtask_{idx}",
            "messages": next_state.get("messages", []),
            "mode": "auto",
        }

        try:
            if sub_intent == "tool_only":
                from supportAgents.agents.action_agent import run_action_agent

                mini_state = run_action_agent(mini_state)
                if not mini_state.get("error"):
                    mini_state = run_answer_agent(mini_state)
            elif sub_intent in {"doc_qa", "code_qa"}:
                mini_state = run_retrieval_agent(mini_state)
                if not mini_state.get("error"):
                    mini_state = run_quality_gate(mini_state)
                    mini_state = run_answer_agent(mini_state)
            else:
                mini_state = run_answer_agent(mini_state)

            executed[idx]["result"] = mini_state.get("answer", "") or mini_state.get("error", "")
        except Exception as exc:
            executed[idx]["result"] = f"[子任务执行失败] {exc}"

    next_state["plan_results"] = executed
    return next_state
