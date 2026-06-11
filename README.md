<img width="2503" height="1386" alt="image" src="https://github.com/user-attachments/assets/3275db1c-8afd-4a30-a99b-982fdf9d33d5" />

# Support Copilot

面向企业内部支持场景的 Multi-Agent RAG 系统。接入飞书文档 / 导入文件 / 接口说明 / 故障案例，通过混合检索 + LLM 生成基于知识的问答，并为复杂问题提供 `planner -> execute -> reflection -> synthesizer` 闭环，同时将短期会话记忆和可复用经验沉淀到数据库。

## 架构概览

```
用户请求 → FastAPI → LangGraph
                     ├─ orchestrator → 简单问题直答 / 检索 / 工具
                     ├─ planner → execute_subtasks → plan_reflection
                     │                                  ├─ finish  → synthesizer
                     │                                  ├─ retry   → execute_subtasks
                     │                                  └─ replan  → planner
                     ├─ retrieval_agent  → PostgreSQL + pgvector (BM25 + Vector + RRF + Rerank)
                     ├─ action_agent     → 工具调用 (pg_query / tavily_search 等)
                     └─ memory           → sessions.state / user_memory / task_memory
```

| 模块 | 职责 |
|------|------|
| `supportAgents/` | 多 Agent 协同：orchestrator / planner / retrieval / action / reflection / synthesizer，基于 LangGraph |
| `rag/` | 文档加载 (飞书 / 本地)、切片、向量化 (DashScope)、混合检索 (向量 + BM25 + RRF)、Rerank、入库 |
| `memory/` | 短期会话记忆压缩、用户画像读取、task_memory 检索、sessions 状态持久化 |
| `api/` | FastAPI REST 接口，含 CORS 支持，Swagger (`/docs`) + Scalar (`/scalar`) 双文档 |
| `cli/` | CLI 入口，支持单文档/目录/飞书 wiki 的索引和查询 |
| `frontend/` | Vite 前端 (开发端口 5173) |

## 关键能力

- **复杂问题闭环执行**：复杂问题会先进入 `planner`，拆解成有依赖关系的子任务，再由 `plan_reflection` 判断是直接收敛、重试低质量任务，还是补规划后继续执行。
- **降级收口**：达到最大反思轮次后，系统会明确区分 `resolved / degraded / failed`，在最终回答中说明已确认内容、未解决点和下一步建议。
- **短期记忆**：保留最近 20 轮原始对话；更早的历史会基于旧 `SessionSummary` 和超窗消息压缩成新的结构化摘要，字段包括 `summary / key_facts / open_issues / failed_attempts / current_goal`。
- **长期记忆**：`user_memory` 存用户长期稳定信息，`task_memory` 存可复用排查经验；planner 前会检索少量高相关 `task_memory` 作为补充上下文。

## 技术亮点

- **多 Agent 闭环编排**：基于 LangGraph 搭建 `orchestrator / planner / retrieval / action / reflection / synthesizer` 协作链路，让复杂问题具备“拆解执行、结果复盘、补规划重试、最终收口”的完整闭环，而不是一次检索后直接回答。
- **混合检索增强 RAG**：检索链路结合 `BM25 + Vector + RRF + Rerank`，并引入 `Query Rewrite / Contextual Retrieval / HyDE` 等增强策略，兼顾术语精确匹配和语义召回，适合接口说明、故障案例、内部文档等复杂企业知识场景。
- **可控的反思与降级机制**：为 planner 链路加入 `plan_reflection`，支持 `finish / retry / replan` 三种动作，并通过最大反思轮次、`resolved / degraded / failed` 状态和结构化日志控制复杂链路发散风险。
- **分层记忆设计**：短期记忆采用“最近 20 轮原始对话 + 结构化 SessionSummary”双层模式，长期记忆拆分为 `user_profile` 与 `task_memory`，分别走直接注入和检索注入两种路径，兼顾连续会话体验与跨会话经验复用。
- **工程化后端能力**：基于 FastAPI 提供文档入库、检索、问答、对话、评测等完整接口；数据库使用 PostgreSQL + pgvector 持久化知识和记忆；同时保留 CLI 和前端入口，便于本地调试、联调和后续扩展。

## 快速开始

### 1. 环境要求

- Python ≥ 3.10
- PostgreSQL 15+ 且已安装 [pgvector](https://github.com/pgvector/pgvector) 扩展
- [飞书应用](https://open.feishu.cn) (如需接入飞书文档)

### 2. 安装

```bash
pip install -e .
```

### 3. 配置

```bash
cp rag/config_local.example.py rag/config_local.py
```

编辑 `rag/config_local.py`，填入私有配置：

| 配置段 | 说明 |
|--------|------|
| `feishu.app_id / app_secret` | 飞书应用凭证 |
| `dashscope.api_key` | 阿里百炼 API Key (embedding) |
| `gemini.api_key` | Gemini API Key (飞书图片多模态识别) |
| `postgres.jdbc_url / user / password` | PostgreSQL 连接信息 |
| `rag.chunk_size / chunk_overlap / batch_size` | 切片与向量化参数 |

也可以通过环境变量配置（优先级低于 `config_local.py`）：

| 环境变量 | 对应配置 |
|----------|----------|
| `FEISHU_APP_ID` | 飞书 App ID |
| `FEISHU_APP_SECRET` | 飞书 App Secret |
| `DASHSCOPE_API_KEY` | 百炼 API Key |
| `GEMINI_API_KEY` | Gemini API Key |
| `POSTGRES_JDBC_URL` | PG 连接串 |
| `POSTGRES_USER` | PG 用户名 |
| `POSTGRES_PASSWORD` | PG 密码 |

### 4. 数据库初始化

```bash
psql -h <host> -U <user> -d <dbname> -f aatarget/db.sql
```

后续迁移文件按序号依次执行，例如：

```bash
psql -h <host> -U <user> -d <dbname> -f aatarget/migration_001_source_unique_hash.sql
psql -h <host> -U <user> -d <dbname> -f aatarget/migration_002_memory_indexes.sql
```

### 5. 启动

```bash
uvicorn main:app --reload
# → Swagger: http://127.0.0.1:8000/docs
# → Scalar:  http://127.0.0.1:8000/scalar
```

## 数据导入

### CLI

```bash
# 单个本地文件
support-copilot index --source ./docs/faq.md

# 整个目录
support-copilot index-dir --source-dir ./docs/

# 单篇飞书文档
support-copilot index-feishu --doc-id <doc_id>

# 飞书 wiki 子树 (递归导入所有 docx + 导入的 md 文件)
support-copilot index-feishu-space \
    --space-id <space_id> \
    --parent-node-token <node_token>
```

### API

```
POST /api/v1/ingestion/file             # 导入本地文件
POST /api/v1/ingestion/directory        # 批量导入目录
POST /api/v1/ingestion/feishu/doc       # 导入飞书单文档
POST /api/v1/ingestion/feishu/wiki-subtree  # 递归导入飞书 wiki 子树
```

重复导入同一文档会自动跳过（按 `source + content_hash` 去重，且 `source` 列有 UNIQUE 约束防并发写重复）。

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/ingestion/*` | 文档入库 |
| POST | `/api/v1/retrieval` | 检索 (混合检索 + Rerank + Query Rewrite) |
| POST | `/api/v1/answering` | RAG 问答 |
| POST | `/api/v1/chat/respond` | Multi-Agent 对话 |
| POST | `/api/v1/evaluation` | 检索评估 |
| GET | `/api/v1/health` | 健康检查 |

## 目录结构

```
.
├── main.py                  # FastAPI 应用入口
├── pyproject.toml           # 项目元信息与依赖
├── aatarget/
│   ├── db.sql               # 建表 DDL
│   └── migration_*.sql      # 增量迁移
├── api/
│   ├── schemas.py           # Pydantic 请求/响应模型
│   └── routers/             # 各业务路由
├── cli/
│   ├── args.py              # CLI 参数定义
│   └── handlers.py          # CLI 命令路由
├── rag/
│   ├── config.py            # 配置加载 (优先级: config_local.py > 环境变量)
│   ├── config_local.example.py
│   ├── feishu_loader.py     # 飞书文档/文件加载
│   ├── ingestion.py         # 文档入库 (切片、向量化、写 PG)
│   ├── indexing.py          # 本地索引构建
│   ├── retrieval.py         # 混合检索 + Rerank
│   ├── embeddings.py        # DashScope embedding 客户端
│   ├── db.py                # PostgreSQL 连接
│   └── eval/                # 检索评估数据集与工具
├── memory/
│   ├── session_memory.py    # 短期记忆压缩与 sessions.state 持久化
│   ├── user_profile.py      # 用户长期信息读取
│   ├── task_memory.py       # planner 前 task_memory 检索
│   ├── db.py                # memory 相关 DB 访问
│   └── models.py            # memory 结构定义
├── supportAgents/
│   ├── graph/               # LangGraph 状态图构建
│   ├── agents/              # orchestrator / planner / reflection / synthesizer 等
│   ├── llm_clients/         # LLM 客户端封装
│   └── tools/               # Agent 可调用工具 (pg_query 等)
├── frontend/                # Vite 前端
├── scripts/                 # 调试与辅助脚本
└── resources/
    ├── models/              # 本地模型 (BGE Reranker)
    └── testdata/            # 测试数据
```

