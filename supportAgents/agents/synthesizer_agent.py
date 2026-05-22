import os

from langchain_core.messages import HumanMessage, SystemMessage

from memory import load_user_profile_text
from supportAgents.agents.prompts import SYNTHESIZER_SYSTEM_PROMPT
from supportAgents.graph.state import SupportAgentState, TaskExecutionResult
from supportAgents.llm_clients import create_llm_client


# 作用：构造综合回答使用的模型实例，给复杂任务预留更长超时。
def _build_synthesizer_llm():
    model = os.environ.get("SUPPORT_SYNTHESIZER_MODEL", "deepseek-v4-flash")
    client = create_llm_client("deepseek", model, timeout=60, max_retries=2, temperature=0)
    return client.get_llm()


# 作用：把单个子任务结果整理成可读文本，方便 synthesizer 统一汇总。
def _format_task_result(task_result: TaskExecutionResult) -> str:
    task_id = task_result.get("task_id", -1)
    sub_query = task_result.get("sub_query", "")
    sub_intent = task_result.get("sub_intent", "")
    worker_name = task_result.get("worker_name", "")
    tool_name = task_result.get("tool_name", "")
    status = task_result.get("status", "error")
    summary = task_result.get("summary", "")
    result = task_result.get("result", "")
    confidence = task_result.get("confidence", 0.0)
    missing_info = task_result.get("missing_info", [])
    evidence = task_result.get("evidence", [])
    error = task_result.get("error", "")

    outcome = result if status == "success" else f"执行失败：{error or 'unknown_error'}"
    evidence_lines = [
        f"- [{item.get('kind', '')}] {item.get('source', '')} score={float(item.get('score', 0.0)):.2f} {item.get('content', '')}"
        for item in evidence
    ]
    evidence_text = "\n".join(evidence_lines) if evidence_lines else "- 无"
    missing_text = "；".join(missing_info) if missing_info else "无"

    return (
        f"--- 子任务[{task_id}] ---\n"
        f"问题：{sub_query}\n"
        f"类型：{sub_intent}\n"
        f"执行器：{worker_name}\n"
        f"工具：{tool_name or 'n/a'}\n"
        f"状态：{status}\n"
        f"置信度：{confidence:.2f}\n"
        f"摘要：{summary}\n"
        f"缺失信息：{missing_text}\n"
        f"证据：\n{evidence_text}\n"
        f"结果：{outcome}"
    )


# 作用：从已有执行结果里提取仍然可信的结论，供 degraded 模式直接输出。
def _build_confirmed_points(plan_results: list[TaskExecutionResult]) -> list[str]:
    confirmed_points: list[str] = []
    for result in plan_results:
        if result.get("status") != "success":
            continue
        text = (result.get("summary", "") or result.get("result", "")).strip()
        if text:
            confirmed_points.append(text)
    return confirmed_points[:5]


# 作用：在最终回复前拼接可直接消费的会话记忆，帮助回答更贴合当前目标并避免重复。
def _build_synthesizer_memory_block(state: SupportAgentState) -> str:
    session_memory = (state.get("session_memory") or {}).get("summary", {})
    recent_messages = state.get("recent_messages") or state.get("messages", [])
    try:
        user_profile_text = load_user_profile_text(state.get("user_id", ""))
    except Exception:
        user_profile_text = ""

    lines = [
        "当前 SessionSummary：",
        f"- summary: {session_memory.get('summary', '')}",
        f"- current_goal: {session_memory.get('current_goal', '')}",
        f"- key_facts: {session_memory.get('key_facts', [])}",
        "",
        "最近 20 轮原始对话：",
    ]
    for message in recent_messages:
        role = message.get("role", "user")
        content = (message.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    if user_profile_text:
        lines.extend(["", user_profile_text])
    return "\n".join(lines)


# 作用：在 degraded/failed 模式下构造更诚实的降级答案，而不是只给一行免责声明。
def _build_degraded_answer(state: SupportAgentState) -> str:
    plan_results = state.get("plan_results") or []
    reflection = state.get("reflection") or {}
    final_status = state.get("final_status", "degraded")
    confirmed_points = _build_confirmed_points(plan_results)
    gaps = reflection.get("gaps", [])

    if final_status == "failed":
        missing_text = "；".join(gaps) if gaps else "当前缺少足够有效的执行结果。"
        return (
            "当前无法给出可靠答案。\n"
            f"原因：{reflection.get('reflection_summary', '多轮反思后仍缺少足够证据。')}\n"
            f"未解决点：{missing_text}\n"
            "建议下一步：补充更具体的报错信息、日志片段、接口名、SQL 查询结果或相关文档后再继续分析。"
        )

    confirmed_text = "\n".join(f"- {item}" for item in confirmed_points) if confirmed_points else "- 暂无可确认结论"
    gaps_text = "\n".join(f"- {item}" for item in gaps) if gaps else "- 当前没有额外缺口说明"
    return (
        "当前回答基于已成功完成的子任务结果整理，以下结论可作为排查起点，但仍有部分关键证据缺失。\n"
        "已确认的部分：\n"
        f"{confirmed_text}\n"
        "暂未确认的部分：\n"
        f"{gaps_text}\n"
        "建议下一步：优先补充上述缺失信息，或转人工结合日志、数据库状态和调用链继续排查。"
    )


# 作用：把各子任务执行结果综合成最终答案，并在降级态下明确说明可信范围和未解决点。
def run_synthesizer(state: SupportAgentState) -> SupportAgentState:
    next_state: SupportAgentState = dict(state)
    if next_state.get("error"):
        next_state["final_status"] = "failed"
        next_state["answer"] = f"Planner 执行失败：{next_state['error']}"
        return next_state

    query = next_state.get("user_query", "")
    plan = next_state.get("plan") or {}
    plan_reason = plan.get("plan_reason", "")
    plan_results = next_state.get("plan_results") or []
    reflection = next_state.get("reflection") or {}
    final_status = next_state.get("final_status", "resolved")

    results_lines = [_format_task_result(task_result) for task_result in plan_results]
    if not results_lines:
        answer = "无法完成综合：所有子任务均未产生结果。"
        next_state["final_status"] = "failed"
        next_state["synthesized_answer"] = answer
        next_state["answer"] = answer
        return next_state

    if final_status in {"degraded", "failed"}:
        answer = _build_degraded_answer(next_state)
        next_state["synthesized_answer"] = answer
        next_state["answer"] = answer
        return next_state

    results_text = "\n\n".join(results_lines)
    reflection_summary = reflection.get("reflection_summary", "")
    gaps = reflection.get("gaps", [])
    memory_block = _build_synthesizer_memory_block(next_state)

    try:
        llm = _build_synthesizer_llm()
        response = llm.invoke(
            [
                SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"用户原始问题：{query}\n"
                        f"分解思路：{plan_reason}\n"
                        f"{memory_block}\n"
                        f"最终 reflection 摘要：{reflection_summary}\n"
                        f"仍需说明的缺口：{gaps}\n\n"
                        "以下是各子任务的结构化执行结果，请综合为一份完整回答：\n\n"
                        f"{results_text}"
                    )
                ),
            ]
        )
        answer = getattr(response, "content", "") or ""
    except Exception:
        # 作用：综合模型失败时保留兜底文本，避免整条复杂链路没有结果。
        answer = (
            f"以下基于各子任务结果汇总。\n"
            f"reflection 摘要：{reflection_summary}\n"
            f"仍有缺口：{gaps}\n\n"
            f"{results_text}"
        )

    next_state["synthesized_answer"] = answer
    next_state["answer"] = answer
    return next_state
