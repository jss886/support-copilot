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
    "gemini": {
        "api_key": None,
        "model": "gemini-2.5-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
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
        "reranker_model_path": str(Path(__file__).resolve().parent.parent / "resources" / "models" / "bge-reranker-v2-m3"),
        "reranker_batch_size": 32,
        "reranker_max_length": 512,
    },
}
