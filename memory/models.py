from typing import TypedDict


class SessionSummaryPayload(TypedDict, total=False):
    # 作用：承载短期记忆压缩后的结构化摘要，供 planner 和 synthesizer 直接消费。
    summary: str
    key_facts: list[str]
    open_issues: list[str]
    failed_attempts: list[str]
    current_goal: str


class SessionMemoryState(TypedDict, total=False):
    # 作用：描述会话短期记忆的持久化状态，便于增量压缩最近 20 轮之外的历史消息。
    summary: SessionSummaryPayload
    compressed_message_count: int


class UserProfilePayload(TypedDict, total=False):
    # 作用：承载某个用户的长期稳定信息，默认直接拼接进 prompt。
    profile_facts: list[str]
    preferences: list[str]


class TaskMemoryPayload(TypedDict, total=False):
    # 作用：描述单条可复用 task_memory，供 planner 前检索增强。
    title: str
    problem: str
    resolution: str
    takeaway: str
    score: float
    tags: list[str]
