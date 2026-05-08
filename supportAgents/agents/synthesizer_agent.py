import os

from langchain_core.messages import HumanMessage, SystemMessage

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

    if status == "success":
        outcome = result
    else:
        outcome = f"执行失败：{error or 'unknown_error'}"

    evidence_lines = []
    for item in evidence:
        source = item.get("source", "")
        kind = item.get("kind", "")
        score = item.get("score", 0.0)
        content = item.get("content", "")
        evidence_lines.append(f"- [{kind}] {source} score={score:.2f} {content}")
    missing_text = "；".join(missing_info) if missing_info else "无"
    evidence_text = "\n".join(evidence_lines) if evidence_lines else "- 无"

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


# 作用：将各子任务执行结果综合为最终答案，写入 state["synthesized_answer"] 和 state["answer"]。
def run_synthesizer(state: SupportAgentState) -> SupportAgentState:
    next_state: SupportAgentState = dict(state)
    if next_state.get("error"):
        next_state["answer"] = f"Planner 执行失败：{next_state['error']}"
        return next_state

    query = next_state.get("user_query", "")
    plan = next_state.get("plan") or {}
    plan_reason = plan.get("plan_reason", "")
    plan_results = next_state.get("plan_results") or []

    results_lines = [_format_task_result(task_result) for task_result in plan_results]
    if not results_lines:
        answer = "无法完成综合：所有子任务均未产生结果。"
        next_state["synthesized_answer"] = answer
        next_state["answer"] = answer
        return next_state

    results_text = "\n\n".join(results_lines)

    try:
        llm = _build_synthesizer_llm()
        response = llm.invoke(
            [
                SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"用户原始问题：{query}\n"
                        f"分解思路：{plan_reason}\n\n"
                        "以下是各子任务的结构化执行结果，请综合为一份完整回答：\n\n"
                        f"{results_text}"
                    )
                ),
            ]
        )
        answer = getattr(response, "content", "") or ""
    except Exception:
        # 这里保留直接拼接兜底，避免综合模型失败时整条复杂链路无结果。
        answer = f"以下基于各子任务结果汇总：\n\n{results_text}"

    next_state["synthesized_answer"] = answer
    next_state["answer"] = answer
    return next_state
