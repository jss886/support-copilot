from dataclasses import dataclass
from pathlib import Path

from rag.env_utils import read_env_var


# 配置优先级：
# 1. CLI 参数
# 2. USER_DEFAULTS 中的默认值
# 3. 环境变量，仅在配置项为空时兜底使用
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = PROJECT_ROOT / "resources"
ARTIFACTS_DIR = RESOURCES_DIR / "artifacts"
DOCS_DIR = RESOURCES_DIR / "doc"


USER_DEFAULTS = {
    "dashscope": {
        "api_key": None,
        "model": "text-embedding-v4",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "timeout": 60,
        "default_dimensions": None,
    },
    "feishu": {
        "app_id": None,
        "app_secret": None,
        "open_api_base": "https://open.feishu.cn/open-apis",
    },
    "gemini": {
        "api_key": None,
        "model": "gemini-2.5-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
    },
    "postgres": {
        "jdbc_url": None,
        "user": None,
        "password": None,
        "text_search_config": "simple",
        "connect_timeout": 5,
    },
    "tavily": {
        "api_key": None,
        "api_base_url": "https://api.tavily.com",
    },
    "rag": {
        "index_file": str(ARTIFACTS_DIR / "basic_rag_index.json"),
        "chunk_size": 500,
        "chunk_overlap": 100,
        "batch_size": 8,
        "retrieval_candidate_top_k": 20,
        "retrieval_final_top_k": 5,
        "enable_query_enhancement": True,
        "query_enhancement_mode": "fast",
        "enable_semantic_query_expansion": True,
        "query_enhancement_model": "deepseek-chat",
        "enable_contextual_retrieval": True,
        "contextual_retrieval_model": "deepseek-chat",
        "contextual_retrieval_max_document_chars": 4000,
        "contextual_retrieval_max_context_chars": 120,
        "enable_rerank": True,
        "rerank_mode": "dashscope_api",
        "rerank_model": "qwen3-rerank",
        "rerank_api_url": "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
        "rerank_timeout": 60,
        "reranker_model_path": str(RESOURCES_DIR / "models" / "bge-reranker-v2-m3"),
        "reranker_batch_size": 32,
        "reranker_max_length": 512,
    },
}

try:
    from rag.config_local import LOCAL_OVERRIDES
except ImportError:
    LOCAL_OVERRIDES = {}


@dataclass(frozen=True)
class DashScopeSettings:
    api_key: str | None
    model: str
    base_url: str
    timeout: int
    default_dimensions: int | None


@dataclass(frozen=True)
class FeishuSettings:
    app_id: str | None
    app_secret: str | None
    open_api_base: str


@dataclass(frozen=True)
class GeminiSettings:
    api_key: str | None
    model: str
    base_url: str


@dataclass(frozen=True)
class PostgresSettings:
    jdbc_url: str | None
    user: str | None
    password: str | None
    text_search_config: str
    connect_timeout: int


@dataclass(frozen=True)
class TavilySettings:
    api_key: str | None
    api_base_url: str


@dataclass(frozen=True)
class RagSettings:
    index_file: str
    chunk_size: int
    chunk_overlap: int
    batch_size: int
    retrieval_candidate_top_k: int
    retrieval_final_top_k: int
    enable_query_enhancement: bool
    query_enhancement_mode: str
    enable_semantic_query_expansion: bool
    query_enhancement_model: str
    enable_contextual_retrieval: bool
    contextual_retrieval_model: str
    contextual_retrieval_max_document_chars: int
    contextual_retrieval_max_context_chars: int
    enable_rerank: bool
    rerank_mode: str
    rerank_model: str
    rerank_api_url: str
    rerank_timeout: int
    reranker_model_path: str
    reranker_batch_size: int
    reranker_max_length: int


@dataclass(frozen=True)
class AppSettings:
    dashscope: DashScopeSettings
    feishu: FeishuSettings
    gemini: GeminiSettings
    postgres: PostgresSettings
    tavily: TavilySettings
    rag: RagSettings


def _read_int_env(name: str, default: int | None) -> int | None:
    value = read_env_var(name)
    if value is None or value == "":
        return default
    return int(value)


def _prefer_config(value: str | None, env_name: str) -> str | None:
    if value not in (None, ""):
        return value
    return read_env_var(env_name)


def _prefer_config_int(value: int | None, env_name: str) -> int | None:
    if value is not None:
        return value
    return _read_int_env(env_name, None)


def _prefer_config_bool(value: bool | None, env_name: str) -> bool | None:
    if value is not None:
        return value
    env_value = read_env_var(env_name)
    if env_value is None or env_value == "":
        return None
    return env_value.lower() in {"1", "true", "yes", "on"}


def _merge_section(section_name: str) -> dict:
    merged = dict(USER_DEFAULTS[section_name])
    merged.update(LOCAL_OVERRIDES.get(section_name, {}))
    return merged


# 作用：优先读取新配置键，缺失时再兼容旧键，避免现有本地配置立即失效。
def _prefer_rag_compat_value(rag_defaults: dict, new_key: str, old_key: str) -> object:
    if new_key in rag_defaults:
        return rag_defaults[new_key]
    return rag_defaults.get(old_key)


# 作用：环境变量优先读新名字，兼容层再兜底旧名字，便于逐步迁移本地部署配置。
def _prefer_compat_env(value: str | None, primary_env: str, legacy_env: str) -> str | None:
    resolved = _prefer_config(value, primary_env)
    if resolved not in (None, ""):
        return resolved
    return read_env_var(legacy_env)


# 作用：布尔配置同样优先读新环境变量，缺失时再兼容旧名字。
def _prefer_compat_bool_env(value: bool | None, primary_env: str, legacy_env: str) -> bool | None:
    resolved = _prefer_config_bool(value, primary_env)
    if resolved is not None:
        return resolved
    return _prefer_config_bool(None, legacy_env)


# 作用：统一解析 rerank 模式；如果显式关闭 rerank，则直接退化为 disabled。
def _resolve_rerank_mode(rag_defaults: dict, enable_rerank: bool | None) -> str:
    resolved_mode = _prefer_config(
        rag_defaults.get("rerank_mode"),
        "RAG_RERANK_MODE",
    ) or "dashscope_api"
    if enable_rerank is False:
        return "disabled"
    return resolved_mode


def load_settings() -> AppSettings:
    dashscope_defaults = _merge_section("dashscope")
    feishu_defaults = _merge_section("feishu")
    gemini_defaults = _merge_section("gemini")
    postgres_defaults = _merge_section("postgres")
    tavily_defaults = _merge_section("tavily")
    rag_defaults = _merge_section("rag")
    resolved_enable_rerank = _prefer_config_bool(
        rag_defaults["enable_rerank"],
        "RAG_ENABLE_RERANK",
    )
    resolved_enable_query_rewrite = _prefer_config_bool(
        _prefer_rag_compat_value(rag_defaults, "enable_query_enhancement", "enable_query_rewrite"),
        "RAG_ENABLE_QUERY_ENHANCEMENT",
    )
    if resolved_enable_query_rewrite is None:
        resolved_enable_query_rewrite = _prefer_config_bool(None, "RAG_ENABLE_QUERY_REWRITE")
    resolved_enable_llm_query_rewrite = _prefer_compat_bool_env(
        _prefer_rag_compat_value(
            rag_defaults,
            "enable_semantic_query_expansion",
            "enable_llm_query_rewrite",
        ),
        "RAG_ENABLE_SEMANTIC_QUERY_EXPANSION",
        "RAG_ENABLE_LLM_QUERY_REWRITE",
    )
    resolved_enable_contextual_retrieval = _prefer_config_bool(
        rag_defaults["enable_contextual_retrieval"],
        "RAG_ENABLE_CONTEXTUAL_RETRIEVAL",
    )

    return AppSettings(
        dashscope=DashScopeSettings(
            api_key=_prefer_config(dashscope_defaults["api_key"], "DASHSCOPE_API_KEY"),
            model=_prefer_config(dashscope_defaults["model"], "DASHSCOPE_MODEL")
            or "text-embedding-v4",
            base_url=_prefer_config(dashscope_defaults["base_url"], "DASHSCOPE_BASE_URL")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            timeout=_prefer_config_int(dashscope_defaults["timeout"], "DASHSCOPE_TIMEOUT")
            or 60,
            default_dimensions=_prefer_config_int(
                dashscope_defaults["default_dimensions"],
                "DASHSCOPE_EMBEDDING_DIMENSIONS",
            ),
        ),
        feishu=FeishuSettings(
            app_id=_prefer_config(feishu_defaults["app_id"], "FEISHU_APP_ID"),
            app_secret=_prefer_config(feishu_defaults["app_secret"], "FEISHU_APP_SECRET"),
            open_api_base=_prefer_config(
                feishu_defaults["open_api_base"], "FEISHU_OPEN_API_BASE"
            )
            or "https://open.feishu.cn/open-apis",
        ),
        gemini=GeminiSettings(
            api_key=_prefer_config(gemini_defaults["api_key"], "GEMINI_API_KEY"),
            model=_prefer_config(gemini_defaults["model"], "GEMINI_MODEL")
            or "gemini-2.5-flash",
            base_url=_prefer_config(gemini_defaults["base_url"], "GEMINI_BASE_URL")
            or "https://generativelanguage.googleapis.com/v1beta",
        ),
        postgres=PostgresSettings(
            jdbc_url=_prefer_config(postgres_defaults["jdbc_url"], "POSTGRES_JDBC_URL"),
            user=_prefer_config(postgres_defaults["user"], "POSTGRES_USER"),
            password=_prefer_config(postgres_defaults["password"], "POSTGRES_PASSWORD"),
            text_search_config=_prefer_config(
                postgres_defaults["text_search_config"], "POSTGRES_TEXT_SEARCH_CONFIG"
            )
            or "simple",
            connect_timeout=_prefer_config_int(
                postgres_defaults["connect_timeout"],
                "POSTGRES_CONNECT_TIMEOUT",
            )
            or 5,
        ),
        tavily=TavilySettings(
            api_key=_prefer_config(tavily_defaults["api_key"], "TAVILY_API_KEY"),
            api_base_url=_prefer_config(
                tavily_defaults["api_base_url"], "TAVILY_API_BASE_URL"
            )
            or "https://api.tavily.com",
        ),
        rag=RagSettings(
            index_file=_prefer_config(rag_defaults["index_file"], "RAG_INDEX_FILE")
            or str(ARTIFACTS_DIR / "basic_rag_index.json"),
            chunk_size=_prefer_config_int(rag_defaults["chunk_size"], "RAG_CHUNK_SIZE")
            or 500,
            chunk_overlap=_prefer_config_int(
                rag_defaults["chunk_overlap"], "RAG_CHUNK_OVERLAP"
            )
            or 100,
            batch_size=_prefer_config_int(rag_defaults["batch_size"], "RAG_BATCH_SIZE")
            or 8,
            retrieval_candidate_top_k=_prefer_config_int(
                rag_defaults["retrieval_candidate_top_k"],
                "RAG_RETRIEVAL_CANDIDATE_TOP_K",
            )
            or 20,
            retrieval_final_top_k=_prefer_config_int(
                rag_defaults["retrieval_final_top_k"],
                "RAG_RETRIEVAL_FINAL_TOP_K",
            )
            or 5,
            enable_query_enhancement=(
                True if resolved_enable_query_rewrite is None else resolved_enable_query_rewrite
            ),
            query_enhancement_mode=_prefer_config(
                _prefer_rag_compat_value(
                    rag_defaults,
                    "query_enhancement_mode",
                    "query_rewrite_mode",
                ),
                "RAG_QUERY_ENHANCEMENT_MODE",
            )
            or read_env_var("RAG_QUERY_REWRITE_MODE")
            or "fast",
            enable_semantic_query_expansion=(
                True
                if resolved_enable_llm_query_rewrite is None
                else resolved_enable_llm_query_rewrite
            ),
            query_enhancement_model=_prefer_compat_env(
                _prefer_rag_compat_value(
                    rag_defaults,
                    "query_enhancement_model",
                    "query_rewrite_model",
                ),
                "RAG_QUERY_ENHANCEMENT_MODEL",
                "RAG_QUERY_REWRITE_MODEL",
            )
            or "deepseek-chat",
            enable_contextual_retrieval=(
                True
                if resolved_enable_contextual_retrieval is None
                else resolved_enable_contextual_retrieval
            ),
            contextual_retrieval_model=_prefer_config(
                rag_defaults["contextual_retrieval_model"],
                "RAG_CONTEXTUAL_RETRIEVAL_MODEL",
            )
            or "deepseek-chat",
            contextual_retrieval_max_document_chars=_prefer_config_int(
                rag_defaults["contextual_retrieval_max_document_chars"],
                "RAG_CONTEXTUAL_RETRIEVAL_MAX_DOCUMENT_CHARS",
            )
            or 4000,
            contextual_retrieval_max_context_chars=_prefer_config_int(
                rag_defaults["contextual_retrieval_max_context_chars"],
                "RAG_CONTEXTUAL_RETRIEVAL_MAX_CONTEXT_CHARS",
            )
            or 120,
            enable_rerank=True if resolved_enable_rerank is None else resolved_enable_rerank,
            rerank_mode=_resolve_rerank_mode(rag_defaults, resolved_enable_rerank),
            rerank_model=_prefer_config(
                rag_defaults.get("rerank_model"),
                "RAG_RERANK_MODEL",
            )
            or "qwen3-rerank",
            rerank_api_url=_prefer_config(
                rag_defaults.get("rerank_api_url"),
                "RAG_RERANK_API_URL",
            )
            or "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
            rerank_timeout=_prefer_config_int(
                rag_defaults.get("rerank_timeout"),
                "RAG_RERANK_TIMEOUT",
            )
            or 60,
            reranker_model_path=_prefer_config(
                rag_defaults["reranker_model_path"],
                "RAG_RERANKER_MODEL_PATH",
            )
            or str(RESOURCES_DIR / "models" / "bge-reranker-v2-m3"),
            reranker_batch_size=_prefer_config_int(
                rag_defaults["reranker_batch_size"],
                "RAG_RERANKER_BATCH_SIZE",
            )
            or 32,
            reranker_max_length=_prefer_config_int(
                rag_defaults["reranker_max_length"],
                "RAG_RERANKER_MAX_LENGTH",
            )
            or 512,
        ),
    )


settings = load_settings()
