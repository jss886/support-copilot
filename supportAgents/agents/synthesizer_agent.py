import os

from langchain_core.messages import HumanMessage, SystemMessage

from supportAgents.agents.prompts import SYNTHESIZER_SYSTEM_PROMPT
from supportAgents.graph.state import SupportAgentState
from supportAgents.llm_clients import create_llm_client


def _build_synthesizer_llm():
    model = os.environ.get("SUPPORT_SYNTHESIZER_MODEL", "deepseek-v4-flash")
    client = create_llm_client("deepseek", model, timeout=60, max_retries=2, temperature=0)
    return client.get_llm()


def run_synthesizer(state: SupportAgentState) -> SupportAgentState:
    """将各子任务执行结果综合为最终答案，写入 state["synthesized_answer"] 和 state["answer"]."""
    next_state: SupportAgentState = dict(state)
    if next_state.get("error"):
        next_state["answer"] = f"Planner 执行失败：{next_state['error']}"
        return next_state

    query = next_state.get("user_query", "")
    plan = next_state.get("plan") or {}
    plan_reason = plan.get("plan_reason", "")
    plan_results = next_state.get("plan_results") or []

    # 构造子任务结果文本
    results_lines: list[str] = []
    for i, st in enumerate(plan_results):
        sub_query = st.get("sub_query", "")
        sub_intent = st.get("sub_intent", "")
        result = st.get("result", "")
        results_lines.append(
            f"--- 子任务 [{i}] ---\n"
            f"问题：{sub_query}\n"
            f"类型：{sub_intent}\n"
            f"结果：{result}"
        )

    if not results_lines:
        results_text = "所有子任务均未产生结果。"
        # 降级：直接拼接，不经过 LLM
        answer = f"无法完成综合：\n{results_text}"
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
                        "以下是各子任务的检索/执行结果，请综合为一份完整回答：\n\n"
                        f"{results_text}"
                    )
                ),
            ]
        )
        answer = getattr(response, "content", "") or ""
    except Exception:
        # LLM 调用失败，直接拼接子任务结果
        answer = f"以下基于各子任务结果汇总：\n\n{results_text}"

    next_state["synthesized_answer"] = answer
    next_state["answer"] = answer
    return next_state
