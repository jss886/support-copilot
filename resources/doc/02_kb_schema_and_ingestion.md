# 知识库表结构与入库设计

## 总体设计

项目当前使用 PostgreSQL 作为文本和结构化信息的主存储，同时使用 pgvector 保存向量字段。知识入库时，需要区分文档级信息和切片级信息。

## 主要表

### kb_documents

`kb_documents` 用于保存文档级元信息，例如文档标题、来源、所属仓库、模块名、作者、标签和版本号。每一篇文档在该表中对应一条记录。

### kb_chunks

`kb_chunks` 用于保存文档切片。每个 chunk 应包含以下信息：

- `document_id`：关联到 `kb_documents`
- `chunk_index`：切片顺序
- `content`：切片原文
- `content_summary`：可选摘要
- `token_count`：文本长度或 token 数
- `keywords`：关键词
- `tsv`：全文检索字段
- `embedding`：1536 维向量
- `metadata`：扩展信息

## 入库流程建议

1. 先在 `kb_documents` 插入一条文档记录。
2. 对正文切片。
3. 为每个切片生成 embedding。
4. 将切片文本、元数据、embedding 一起写入 `kb_chunks`。

## 为什么要同时保存文本和向量

只保存向量无法支持 BM25、关键词过滤、片段展示和来源追踪，因此 `content` 必须保留。只保存文本又无法支持语义检索，因此还需要 `embedding` 字段。

## 推荐的检索策略

推荐采用混合检索：

- 向量检索负责语义相似召回
- BM25 负责术语、接口名和错误码的精确召回
- 最终使用 RRF 融合两路结果
- 必要时增加 rerank 模型进行精排

## 对当前 Demo 的影响

`basic_rag.py` 当前先把 embedding 落到本地 JSON 文件中，目的是先验证 embedding 与检索效果。后续接入数据库时，`ChunkRecord` 中的 `text` 和 `embedding` 可以直接映射到 `kb_chunks.content` 与 `kb_chunks.embedding`。
