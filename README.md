# Support Copilot

面向企业内部支持场景的 Multi-Agent RAG 系统。接入飞书文档 / 导入文件 / 接口说明 / 故障案例，通过混合检索 + LLM 生成基于知识的问答，并将对话中的可复用经验沉淀到 task_memory。

## 架构概览

```
用户请求 → FastAPI → Agent Router (LangGraph)
                         ├─ retrieval_agent  → PostgreSQL + pgvector (混合检索 + Rerank)
                         ├─ action_agent     → 工具调用 (pg_query 等)
                         ├─ answer_agent     → DeepSeek LLM 生成回答
                         └─ memory_agent     → 经验写入 task_memory
```

| 模块 | 职责 |
|------|------|
| `supportAgents/` | 多 Agent 协同：routing / retrieval / action / answer / memory，基于 LangGraph |
| `rag/` | 文档加载 (飞书 / 本地)、切片、向量化 (DashScope)、混合检索 (向量 + BM25)、Rerank (BGE)、入库 |
| `api/` | FastAPI REST 接口，含 CORS 支持，Swagger (`/docs`) + Scalar (`/scalar`) 双文档 |
| `cli/` | CLI 入口，支持单文档/目录/飞书 wiki 的索引和查询 |
| `frontend/` | Vite 前端 (开发端口 5173) |

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

后续迁移文件（如 `aatarget/migration_001_source_unique_hash.sql`）按序号依次执行。

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
| POST | `/api/v1/chat` | Multi-Agent 对话 |
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
├── supportAgents/
│   ├── graph/               # LangGraph 状态图构建
│   ├── agents/               # 各 Agent 实现
│   ├── llm_clients/         # LLM 客户端封装
│   └── tools/               # Agent 可调用工具 (pg_query 等)
├── frontend/                # Vite 前端
├── scripts/                 # 调试与辅助脚本
└── resources/
    ├── models/              # 本地模型 (BGE Reranker)
    └── testdata/            # 测试数据
```

## 开发备忘

- **调试 Agent 链路**：`python scripts/debug_graph.py`
- **调试飞书图片识别**：`python scripts/debug_image_caption.py --doc-id <doc_id>`
- **CLI 检索测试**：`support-copilot query --question "xxx" --top-k 5`
- **CLI 问答测试**：`support-copilot answer --question "xxx"`
- **生成评估数据集**：`python -m rag.eval.main`
- 数据库迁移文件在 `aatarget/` 下按序号依次执行
- 本地 Reranker 模型首次运行时会自动从 HuggingFace 下载到 `resources/models/`
