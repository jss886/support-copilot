import os

from langchain_core.messages import HumanMessage, SystemMessage

from supportAgents.agents.prompts import build_answer_system_prompt, build_answer_user_prompt
from supportAgents.graph.state import SupportAgentState
from supportAgents.llm_clients import create_llm_client


# 作用：构造 answer_agent 使用的模型实例，先默认走 DeepSeek，后续再抽到独立配置层。
def _build_answer_llm():
    model = os.environ.get("SUPPORT_AGENTS_MODEL", "deepseek-v4-flash")
    base_url = os.environ.get("SUPPORT_AGENTS_BASE_URL")
    client = create_llm_client(
        "deepseek",
        model,
        base_url=base_url,
        timeout=60,
        max_retries=2,
    )
    return client.get_llm()


# 作用：执行回答节点，统一消费 state 中的路由结果和检索证据并写回最终答案。
def run_answer_agent(state: SupportAgentState) -> SupportAgentState:
    next_state: SupportAgentState = dict(state)
    if next_state.get("error"):
        next_state["answer"] = f"当前流程执行失败：{next_state['error']}"
        return next_state

    llm = _build_answer_llm()
    intent = next_state.get("intent", "direct_answer")
    response = llm.invoke(
        [
            SystemMessage(content=build_answer_system_prompt(intent)),
            HumanMessage(content=build_answer_user_prompt(next_state)),
        ]
    )
    next_state["answer"] = getattr(response, "content", "") or ""
    return next_state
