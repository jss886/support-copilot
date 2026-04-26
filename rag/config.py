from dataclasses import dataclass
from pathlib import Path

from rag.env_utils import read_env_var


# Configuration precedence:
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = PROJECT_ROOT / "resources"
ARTIFACTS_DIR = RESOURCES_DIR / "artifacts"
DOCS_DIR = RESOURCES_DIR / "doc"


# 1. CLI arguments
# 2. Values defined in USER_DEFAULTS below
# 3. Environment variables, used only as fallback when config.py leaves a value empty
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
    "postgres": {
        "jdbc_url": None,
        "user": None,
        "password": None,
        "text_search_config": "simple",
        "connect_timeout": 5,
    },
    "rag": {
        "index_file": str(ARTIFACTS_DIR / "basic_rag_index.json"),
        "chunk_size": 500,
        "chunk_overlap": 100,
        "batch_size": 8,
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
class PostgresSettings:
    jdbc_url: str | None
    user: str | None
    password: str | None
    text_search_config: str
    connect_timeout: int


@dataclass(frozen=True)
class RagSettings:
    index_file: str
    chunk_size: int
    chunk_overlap: int
    batch_size: int


@dataclass(frozen=True)
class AppSettings:
    dashscope: DashScopeSettings
    feishu: FeishuSettings
    postgres: PostgresSettings
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


def _merge_section(section_name: str) -> dict:
    merged = dict(USER_DEFAULTS[section_name])
    merged.update(LOCAL_OVERRIDES.get(section_name, {}))
    return merged


def load_settings() -> AppSettings:
    dashscope_defaults = _merge_section("dashscope")
    feishu_defaults = _merge_section("feishu")
    postgres_defaults = _merge_section("postgres")
    rag_defaults = _merge_section("rag")

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
        ),
    )


settings = load_settings()
