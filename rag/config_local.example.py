from pathlib import Path


ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "resources" / "artifacts"


# Copy this file to `rag/config_local.py` and fill in your own private values.
# `config_local.py` is ignored by git and has higher priority than config.py.
LOCAL_OVERRIDES = {
    "dashscope": {
        "api_key": None,
        "model": "text-embedding-v4",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "timeout": 60,
        "default_dimensions": 1536,
    },
    "feishu": {
        "app_id": None,
        "app_secret": None,
        "open_api_base": "https://open.feishu.cn/open-apis",
    },
    "postgres": {
        "jdbc_url": "jdbc:postgresql://host:5432/dbname",
        "user": "your_user",
        "password": "your_password",
        "text_search_config": "simple",
    },
    "rag": {
        "index_file": str(ARTIFACTS_DIR / "basic_rag_index.json"),
        "chunk_size": 500,
        "chunk_overlap": 100,
        "batch_size": 8,
    },
}
