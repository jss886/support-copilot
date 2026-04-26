from typing import Any

from pydantic import BaseModel, Field


class DatabaseOptions(BaseModel):
    # 作用：承载数据库连接参数，未显式传入时走项目默认配置。
    jdbc_url: str | None = Field(default=None, description="PostgreSQL JDBC 连接串。")
    db_user: str | None = Field(default=None, description="PostgreSQL 用户名。")
    db_password: str | None = Field(default=None, description="PostgreSQL 密码。")


class EmbeddingOptions(BaseModel):
    # 作用：承载向量化相关参数，方便后续扩展不同 embedding 配置。
    embedding_dimensions: int | None = Field(
        default=None,
        ge=1,
        description="向量维度，不传时使用系统默认值。",
    )


class IngestionOptions(BaseModel):
    # 作用：承载文本切片和批量写入参数，供各类入库接口复用。
    chunk_size: int | None = Field(default=None, ge=1, description="切片大小。")
    chunk_overlap: int | None = Field(default=None, ge=0, description="切片重叠长度。")
    batch_size: int | None = Field(default=None, ge=1, description="批量向量化大小。")


class RetrievalOptions(BaseModel):
    # 作用：承载检索请求的通用参数。
    top_k: int = Field(default=3, ge=1, description="返回的召回结果数量。")
    source: str | None = Field(
        default=None,
        description="可选来源过滤，例如 feishu://docx/<doc_id> 或本地文件路径。",
    )


class FileIngestionRequest(DatabaseOptions, EmbeddingOptions, IngestionOptions):
    # 作用：描述单文件入库所需的请求参数。
    source: str = Field(description="本地文件路径。")


class DirectoryIngestionRequest(DatabaseOptions, EmbeddingOptions, IngestionOptions):
    # 作用：描述目录批量入库所需的请求参数。
    source_dir: str = Field(description="包含 Markdown 文件的目录路径。")


class FeishuDocIngestionRequest(DatabaseOptions, EmbeddingOptions, IngestionOptions):
    # 作用：描述单篇飞书文档入库所需的请求参数。
    doc_id: str = Field(description="飞书 Docx 文档 ID。")


class FeishuWikiSubtreeIngestionRequest(DatabaseOptions, EmbeddingOptions, IngestionOptions):
    # 作用：描述飞书知识库节点递归入库所需的请求参数。
    space_id: str = Field(description="飞书知识库空间 ID。")
    parent_node_token: str = Field(description="飞书知识库父节点 token。")


class SeedTestDataRequest(DatabaseOptions, EmbeddingOptions):
    # 作用：描述生成模拟测试数据所需的请求参数。
    doc_count: int = Field(default=100, ge=1, description="生成的文档数量。")
    chunks_per_doc: int = Field(default=5, ge=1, description="每篇文档生成的切片数量。")


class SeedHardNegativesRequest(DatabaseOptions, EmbeddingOptions, IngestionOptions):
    # 作用：描述生成 hard negative 数据所需的请求参数。
    pass


class QueryRequest(BaseModel):
    # 作用：描述检索接口所需的最小请求参数，对外只暴露问题和召回数量。
    question: str = Field(description="用户检索问题。")
    top_k: int = Field(default=3, ge=1, description="返回的召回结果数量。")


class AnswerRequest(BaseModel):
    # 作用：描述问答接口所需的最小请求参数，对外只暴露问题和召回数量。
    question: str = Field(description="用户问答问题。")
    top_k: int = Field(default=3, ge=1, description="参与回答生成的召回结果数量。")


class IngestionResult(BaseModel):
    # 作用：统一描述单次入库的结果信息。
    document_id: str | None = Field(default=None, description="单文档入库时返回的文档 ID。")
    document_count: int = Field(default=0, description="本次处理的文档数量。")
    chunk_count: int = Field(default=0, description="本次写入的切片数量。")


class RetrievalItem(BaseModel):
    # 作用：描述单条召回结果，便于 Swagger 中直接查看字段结构。
    score: float = Field(description="向量召回得分。")
    source: str = Field(description="切片来源。")
    start: int = Field(description="切片起始位置。")
    end: int = Field(description="切片结束位置。")
    text: str = Field(description="切片文本内容。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加元数据。")


class AnswerResult(BaseModel):
    # 作用：描述问答接口返回的最终答案。
    answer: str = Field(description="基于召回上下文生成的答案。")


class RootInfo(BaseModel):
    # 作用：描述服务首页返回的基础访问信息。
    name: str = Field(description="服务名称。")
    docs: str = Field(description="Swagger 文档地址。")
    openapi: str = Field(description="OpenAPI 描述地址。")


class HealthInfo(BaseModel):
    # 作用：描述健康检查的最小状态信息。
    status: str = Field(description="服务状态。")


class ApiResponse(BaseModel):
    # 作用：作为通用响应基类，承载成功标记和提示信息。
    success: bool = Field(default=True, description="本次调用是否成功。")
    message: str = Field(default="ok", description="本次调用的说明信息。")


class RootResponse(ApiResponse):
    # 作用：描述服务首页接口的响应结构。
    data: RootInfo


class HealthResponse(ApiResponse):
    # 作用：描述健康检查接口的响应结构。
    data: HealthInfo


class IngestionResponse(ApiResponse):
    # 作用：描述各类入库和造数接口的统一响应结构。
    data: IngestionResult


class RetrievalResponse(ApiResponse):
    # 作用：描述检索接口的响应结构。
    data: list[RetrievalItem]


class AnswerResponse(ApiResponse):
    # 作用：描述问答接口的响应结构。
    data: AnswerResult
