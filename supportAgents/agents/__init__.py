from importlib import import_module

_EXPORT_MAP = {
    "run_action_agent": ("supportAgents.agents.action_agent", "run_action_agent"),
    "run_answer_agent": ("supportAgents.agents.answer_agent", "run_answer_agent"),
    "decide_intent": ("supportAgents.agents.orchestrator_agent", "decide_intent"),
    "run_orchestrator": ("supportAgents.agents.orchestrator_agent", "run_orchestrator"),
    "run_execute_subtasks": ("supportAgents.agents.planner_agent", "run_execute_subtasks"),
    "run_planner": ("supportAgents.agents.planner_agent", "run_planner"),
    "run_quality_gate": ("supportAgents.agents.quality_gate", "run_quality_gate"),
    "build_context_text": ("supportAgents.agents.retrieval_agent", "build_context_text"),
    "run_retrieval_agent": ("supportAgents.agents.retrieval_agent", "run_retrieval_agent"),
    "run_synthesizer": ("supportAgents.agents.synthesizer_agent", "run_synthesizer"),
    "ACTION_AGENT_SYSTEM_PROMPT": ("supportAgents.agents.prompts", "ACTION_AGENT_SYSTEM_PROMPT"),
    "DEGRADED_ANSWER_SYSTEM_PROMPT": (
        "supportAgents.agents.prompts",
        "DEGRADED_ANSWER_SYSTEM_PROMPT",
    ),
    "DIRECT_ANSWER_SYSTEM_PROMPT": ("supportAgents.agents.prompts", "DIRECT_ANSWER_SYSTEM_PROMPT"),
    "FALLBACK_SYSTEM_PROMPT": ("supportAgents.agents.prompts", "FALLBACK_SYSTEM_PROMPT"),
    "MEMORY_SYSTEM_PROMPT": ("supportAgents.agents.prompts", "MEMORY_SYSTEM_PROMPT"),
    "ORCHESTRATOR_SYSTEM_PROMPT": (
        "supportAgents.agents.prompts",
        "ORCHESTRATOR_SYSTEM_PROMPT",
    ),
    "PLANNER_SYSTEM_PROMPT": ("supportAgents.agents.prompts", "PLANNER_SYSTEM_PROMPT"),
    "RAG_ANSWER_SYSTEM_PROMPT": ("supportAgents.agents.prompts", "RAG_ANSWER_SYSTEM_PROMPT"),
    "SYNTHESIZER_SYSTEM_PROMPT": ("supportAgents.agents.prompts", "SYNTHESIZER_SYSTEM_PROMPT"),
    "TOOL_ONLY_SYSTEM_PROMPT": ("supportAgents.agents.prompts", "TOOL_ONLY_SYSTEM_PROMPT"),
    "TOOL_RESULT_ANSWER_SYSTEM_PROMPT": (
        "supportAgents.agents.prompts",
        "TOOL_RESULT_ANSWER_SYSTEM_PROMPT",
    ),
}

__all__ = list(_EXPORT_MAP)


# 作用：按需懒加载 agents 子模块，减少包初始化时的循环依赖风险。
def __getattr__(name: str):
    if name not in _EXPORT_MAP:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORT_MAP[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
