# Planner 模块实现计划

## 1. 目标

在现有 Multi-Agent RAG 链路中增加 Planner 能力，使系统能自动识别复杂任务并分解执行，同时保持简单任务的现有链路完全不受影响。

## 2. 架构变更

### 2.1 当前流程（不变部分）

```
START -> orchestrator (LLM路由)
  ├── doc_qa/code_qa  -> retrieval -> quality_gate -> answer
  ├── tool_only       -> action -> answer
  └── direct_answer/fallback -> answer -> END
```

### 2.2 变更后流程

```
START -> orchestrator (intent + complexity 一并输出)
  ├── complex  -> planner (分解子任务) -> execute_subtasks -> synthesizer -> END
  └── simple   -> 现有链路，完全不动
```

关键设计决策：**不在 orchestrator 之外新增独立的复杂度判断步骤**，而是在现有 orchestrator 的 LLM 调用中直接多输出一个 `complexity` 字段，零额外 LLM 调用。

## 3. 复杂任务的定义

满足以下任一条件判定为 `complex`：

- 用户问题包含多个独立子问题（如"A 和 B 有什么区别？分别怎么配置？"）
- 需要跨文档/跨来源信息整合才能回答（如"对比接口 X 和接口 Y 的错误处理机制"）
- 回答需要同时依赖知识库检索 + 工具执行
- 问题本身是排查类任务，需要多步推理（如"X 报错了，可能是什么原因？怎么排查？"）
- 问题包含条件分支逻辑（如"如果是 A 场景则 X，如果是 B 场景则 Y"）

简单任务则直接走现有链路，不做任何改动。

## 4. 文件级改动清单

### 4.1 修改现有文件

| 文件 | 改动内容 |
|---|---|
| `supportAgents/graph/state.py` | 新增 `ComplexityType`、`SubTask`、`PlanPayload` 类型；`SupportAgentState` 加 `complexity`、`plan`、`plan_results`、`synthesized_answer` 字段 |
| `supportAgents/agents/prompts.py` | 修改 `ORCHESTRATOR_SYSTEM_PROMPT`，JSON 输出加 `complexity` 字段；新增 Planner 和 Synthesizer 的 system prompt |
| `supportAgents/agents/orchestrator_agent.py` | `_parse_intent_json` 解析新增的 `complexity` 字段并写入 state |
| `supportAgents/graph/builder.py` | 新增 `planner`、`execute_subtasks`、`synthesizer` 三个节点；新增 `_route_after_orchestrator` 的 complex 分支；注册节点和边 |
| `supportAgents/agents/__init__.py` | 导出新增的 agent 函数和 prompt |

### 4.2 新增文件

| 文件 | 职责 |
|---|---|
| `supportAgents/agents/planner_agent.py` | Planner 节点：LLM 将复杂问题分解为有序子任务列表 |
| `supportAgents/agents/synthesizer_agent.py` | Synthesizer 节点：将各子任务结果汇总为最终答案 |

## 5. 详细设计

### 5.1 State 类型扩展（`state.py`）

```python
ComplexityType = Literal["simple", "complex"]

class SubTask(TypedDict, total=False):
    """单个子任务"""
    sub_query: str          # 子问题的独立查询文本
    sub_intent: IntentType  # 子任务的路由意图
    depends_on: list[int]   # 依赖的子任务索引列表，空列表表示无依赖
    result: str             # 子任务执行结果，由 execute_subtasks 填充

class PlanPayload(TypedDict, total=False):
    """Planner 输出的完整计划"""
    original_query: str
    sub_tasks: list[SubTask]
    plan_reason: str        # Planner 解释为什么这样分解

# SupportAgentState 新增字段：
# complexity: ComplexityType
# plan: PlanPayload
# plan_results: list[SubTask]     # 执行完的 sub_tasks，带 result
# synthesized_answer: str         # synthesizer 的最终输出
```

### 5.2 Orchestrator Prompt 修改（`prompts.py`）

在 `ORCHESTRATOR_SYSTEM_PROMPT` 中：

1. 路由类别增加一条说明：复杂任务会被后续 Planner 接管
2. JSON 输出格式加 `complexity` 字段：

```json
{
  "intent": "doc_qa | code_qa | tool_only | direct_answer | fallback",
  "complexity": "simple | complex",
  "reason": "一句简洁中文说明"
}
```

3. 补充 complexity 判断规则（见第 3 节的定义）

### 5.3 Planner 节点（`planner_agent.py`）

**输入**：`user_query`、`intent`、`route_reason`

**处理**：
1. 构造 system prompt（`PLANNER_SYSTEM_PROMPT`），指导 LLM 将复杂问题拆解为有序子任务
2. 每个子任务包含 `sub_query`（独立可检索/可执行的查询文本）、`sub_intent`（路由意图）、`depends_on`（依赖关系）
3. LLM 输出结构化 JSON，解析为 `PlanPayload`

**输出**：写入 `state["plan"]`；写入 `state["intent"]` 保持原值（供后续参考）

**Planner 约束规则**：
- 子任务数量控制在 2-5 个，避免过度拆分
- 子任务之间尽量独立，减少依赖
- 每个 `sub_query` 必须是完整、可独立理解的查询语句
- 依赖关系用索引表示，形成 DAG（不允许循环依赖）
- 子任务的 `sub_intent` 继承自 orchestrator 的整体 intent，除非某个子任务明确需要不同的处理方式

### 5.4 执行子任务节点（`builder.py` 中的 `_execute_subtasks`）

这个节点不新建文件，直接在 `builder.py` 或单独文件中实现，因为它本质是编排逻辑：

```
for each sub_task in topological_order(plan.sub_tasks):
    1. 构造 mini state：
       - user_query = sub_task.sub_query
       - intent = sub_task.sub_intent
       - 如果 sub_task 有依赖，将依赖子任务的结果注入上下文
    2. 根据 sub_intent 路由：
       - doc_qa/code_qa → run_retrieval_agent → run_quality_gate → run_answer_agent
       - tool_only → run_action_agent → run_answer_agent
       - direct_answer → run_answer_agent
    3. sub_task["result"] = mini_state["answer"]
    4. 追加到 plan_results
```

关键点：
- 复用现有 agent 函数（`run_retrieval_agent`、`run_quality_gate`、`run_action_agent`、`run_answer_agent`），不重复实现
- 依赖子任务的结果通过 `user_query` 拼接注入（如"前置信息：xxx\n当前子问题：yyy"）
- 单个子任务失败不中断整体流程，在 result 中标记失败原因

### 5.5 Synthesizer 节点（`synthesizer_agent.py`）

**输入**：原始 `user_query`、`plan`（含分解理由）、`plan_results`（含各子任务结果）

**处理**：
1. 构造 system prompt（`SYNTHESIZER_SYSTEM_PROMPT`），指导 LLM 将各子任务结果综合为一份完整答案
2. 按 plan 的原始分解结构组织信息
3. 标注各部分信息的来源（来自哪个子任务的结果）

**输出**：写入 `state["synthesized_answer"]`，同时写入 `state["answer"]`（作为最终答案的统一出口）

**Synthesizer 约束**：
- 先给总结论，再分点展开
- 保留原始术语、字段名、接口名
- 如果某个子任务未能获取足够信息，明确标注
- 不重复子任务结果中已经注明的不确定性

### 5.6 Graph 构建变更（`builder.py`）

```python
def _route_after_orchestrator(state: SupportAgentState) -> str:
    # 新增：复杂任务走 planner 分支
    complexity = state.get("complexity", "simple")
    if complexity == "complex":
        return "planner"

    intent = state.get("intent", "fallback")
    if intent == "tool_only":
        return "action"
    if intent in {"doc_qa", "code_qa"}:
        return "retrieval"
    return "answer"


def build_support_graph():
    builder = StateGraph(SupportAgentState)

    # 现有节点
    builder.add_node("orchestrator", run_orchestrator)
    builder.add_node("retrieval", run_retrieval_agent)
    builder.add_node("quality_gate", run_quality_gate)
    builder.add_node("action", run_action_agent)
    builder.add_node("answer", run_answer_agent)

    # 新增节点
    builder.add_node("planner", run_planner)
    builder.add_node("execute_subtasks", run_execute_subtasks)
    builder.add_node("synthesizer", run_synthesizer)

    builder.add_edge(START, "orchestrator")
    builder.add_conditional_edges(
        "orchestrator",
        _route_after_orchestrator,
        {
            "planner": "planner",         # 新增
            "retrieval": "retrieval",
            "action": "action",
            "answer": "answer",
        },
    )

    # 现有简单链路
    builder.add_edge("retrieval", "quality_gate")
    builder.add_edge("quality_gate", "answer")
    builder.add_edge("action", "answer")

    # 新增复杂链路
    builder.add_edge("planner", "execute_subtasks")
    builder.add_edge("execute_subtasks", "synthesizer")

    # 统一终点
    builder.add_edge("answer", END)
    builder.add_edge("synthesizer", END)

    return builder.compile()
```

## 6. 实现步骤（按顺序）

### Step 1：扩展 State 类型
- 文件：`supportAgents/graph/state.py`
- 新增 `ComplexityType`、`SubTask`、`PlanPayload`
- `SupportAgentState` 加 4 个新字段

### Step 2：修改 Orchestrator Prompt + 解析逻辑
- 文件：`supportAgents/agents/prompts.py` — 改 `ORCHESTRATOR_SYSTEM_PROMPT`
- 文件：`supportAgents/agents/orchestrator_agent.py` — `_parse_intent_json` 解析 `complexity`，`run_orchestrator` 写入 state

### Step 3：新增 Planner 和 Synthesizer Prompt
- 文件：`supportAgents/agents/prompts.py` — 新增 `PLANNER_SYSTEM_PROMPT`、`SYNTHESIZER_SYSTEM_PROMPT`

### Step 4：实现 Planner Agent
- 文件：`supportAgents/agents/planner_agent.py`（新建）
- LLM 调用，解析子任务 JSON，写入 `state["plan"]`

### Step 5：实现 Synthesizer Agent
- 文件：`supportAgents/agents/synthesizer_agent.py`（新建）
- LLM 调用，汇总子任务结果，写入 `state["synthesized_answer"]` 和 `state["answer"]`

### Step 6：实现 execute_subtasks 编排节点
- 文件：`supportAgents/agents/planner_agent.py` 或独立文件
- 拓扑排序 + 逐个执行子任务，复用现有 agent 函数

### Step 7：修改 Graph Builder
- 文件：`supportAgents/graph/builder.py`
- 注册新节点、改条件路由、加边

### Step 8：更新导出
- 文件：`supportAgents/agents/__init__.py`
- 导出新增函数和 prompt

### Step 9：验证
- 用简单问题测试，确认现有链路不受影响
- 用复杂问题测试 Planner 分解和执行
- 检查异常处理：子任务失败、LLM 解析失败等降级路径

## 7. 降级策略

| 异常场景 | 处理方式 |
|---|---|
| orchestrator 输出 `complexity` 解析失败 | 默认 `simple`，走现有链路 |
| Planner 子任务分解解析失败 | 降级为 simple，直接走现有 retrieval -> answer |
| 单个子任务执行失败 | 在 result 中标记 `[失败] {原因}`，synthesizer 会标注该部分信息缺失 |
| execute_subtasks 整体失败 | 降级：直接用原问题走 retrieval -> answer |
| Synthesizer 调用失败 | 直接将各子任务结果拼接输出（不经过 LLM） |

## 8. 后续可扩展方向（不在本次范围）

- 子任务间支持条件分支（根据前一个子任务的结果决定后续路径）
- 支持人工确认环节（Planner 出计划后暂停，用户确认后再执行）
- 支持子任务并行执行（无依赖关系的子任务并发跑）
- plan 缓存（相似复杂问题复用已有的分解方案）
