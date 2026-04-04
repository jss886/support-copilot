## 1. `planner_agent`

### 作用

负责**理解用户问题 + 拆任务 + 做路由决策**。

### 它回答的问题

- 这是问文档，还是问代码，还是要查系统信息？
- 要不要检索？
- 要不要调工具？
- 是简单问题还是复合问题？

### 输入

- 用户 query
- session context
- user memory summary

### 输出

- `intent`
- `plan`
- `needs_retrieval`
- `needs_tool_call`
- `tool_list`

### 例子

用户问：

> 支付成功但库存没扣，帮我结合文档和历史案例分析一下

它会判断：

- 这是 `retrieval_plus_tool`
- 需要先检索知识库，再查 incident case

------

## 2. `context_agent`

### 作用

负责**把检索出来的内容整理成可用上下文**。

它不是“再回答一次”，而是把杂乱 evidence 变成结构化 context。

### 它做什么

- 去重
- 过滤噪声
- 保留关键 chunk
- 按模块/主题组织内容
- 标注来源

### 输入

- rerank 后的 chunks
- 当前问题

### 输出

- `top_evidence`
- `structured_context`

### 为什么它重要

因为直接把 top-k chunk 生拼给模型，效果通常一般。
 这个 agent 的价值就是做 **context engineering**。

------

## 3. `action_agent`

### 作用

负责**调用工具，获取检索之外的结构化信息**。

### 它处理什么问题

- 查 API 说明
- 查模块依赖
- 查历史 incident
- 查配置项
- 查数据库 schema（可选）

### 输入

- planner 给出的 tool request
- 当前问题
- 可选的 retrieval context

### 输出

- `tool_results`

### 本质

它是“执行型 agent”。

------

## 4. `answer_agent`

### 作用

负责**综合所有信息，生成最终回答**。

### 它整合什么

- 用户问题
- memory summary
- structured context
- tool results

### 输出

- `final_answer`

### 它不是单纯总结

它要做到：

- 给出结论
- 给出依据
- 给出排查建议或下一步动作

------

## 5. `memory_agent`

### 作用

负责**判断这次交互里哪些信息值得沉淀为长期经验**。

### 它做什么

- 判断要不要写 memory
- 提炼 task summary
- 更新 user preference
- 生成可入库的结构化 memory

### 输出

- `memory_write_payload`

### 它的价值

这是你项目里非常重要的亮点：
 不是保存聊天记录，而是**沉淀经验**。