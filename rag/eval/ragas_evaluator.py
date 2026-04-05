import json
import asyncio
import math
import os
from pathlib import Path
from typing import Any

from datasets import Dataset
from langchain_openai import ChatOpenAI
from ragas import evaluate
from ragas.embeddings import BaseRagasEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, ResponseRelevancy

from rag.answering import answer_question
from rag.config import settings
from rag.embeddings import DashScopeEmbeddingClient
from rag.eval.dataset import load_eval_dataset
from rag.retrieval import retrieve


DEFAULT_RAGAS_OUTPUT = Path("resources/eval/ragas_eval_result.json")


class DashScopeRagasEmbeddings(BaseRagasEmbeddings):
    """作用：把项目现有的 DashScope embedding 客户端适配成 RAGAS 接口。"""

    def __init__(self) -> None:
        super().__init__()
        self.client = DashScopeEmbeddingClient()

    def embed_query(self, text: str) -> list[float]:
        return self.client.embed_texts([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.client.embed_texts(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self.embed_query, text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)


def _require_env(name: str) -> str:
    """作用：读取必需的环境变量，缺失时直接抛错。"""
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _build_judge_llm() -> LangchainLLMWrapper:
    """作用：构造用于 RAGAS 评测的 DeepSeek judge model。"""
    model = ChatOpenAI(
        model="deepseek-chat",
        api_key=_require_env("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1",
        temperature=0,
        n=1,
    )
    return LangchainLLMWrapper(model)


def _build_ragas_embeddings() -> DashScopeRagasEmbeddings:
    """作用：构造 RAGAS 需要的 embedding 包装器。"""
    _require_env("DASHSCOPE_API_KEY")
    return DashScopeRagasEmbeddings()


def _build_single_turn_sample(item, top_k: int) -> dict[str, Any]:
    """作用：把当前项目的问答链路转换成 RAGAS 单条评测样本。"""
    retrieved = retrieve(query=item.question, top_k=top_k)
    retrieved_contexts = [record.text for _, record in retrieved]

    # 这里直接复用现有 answer_question，保证 RAGAS 评测和项目当前回答链路一致。
    response = answer_question(question=item.question, top_k=top_k)
    return {
        "user_input": item.question,
        "retrieved_contexts": retrieved_contexts,
        "response": response,
        "reference": "；".join(item.expected_substrings),
    }


def resolve_ragas_output_path(output_path: Path) -> Path:
    """作用：兼容目录或文件路径输入，统一解析成可写的结果文件路径。"""
    if output_path.exists() and output_path.is_dir():
        return output_path / DEFAULT_RAGAS_OUTPUT.name
    if output_path.suffix:
        return output_path
    return output_path / DEFAULT_RAGAS_OUTPUT.name


def build_ragas_dataset(
    *,
    dataset_path: Path,
    top_k: int = 5,
    limit: int | None = None,
) -> Dataset:
    """作用：从现有检索评测集构造 RAGAS 可直接消费的数据集。"""
    items = load_eval_dataset(dataset_path)
    if limit is not None:
        items = items[:limit]

    rows = [_build_single_turn_sample(item, top_k=top_k) for item in items]
    return Dataset.from_list(rows)


def evaluate_ragas_metrics(
    *,
    dataset_path: Path,
    top_k: int = 5,
    limit: int | None = None,
    output_path: Path = DEFAULT_RAGAS_OUTPUT,
) -> dict[str, Any]:
    """作用：执行 RAGAS 忠实度与回答相关性评测，并落盘结果。"""
    resolved_output_path = resolve_ragas_output_path(output_path)
    dataset = build_ragas_dataset(
        dataset_path=dataset_path,
        top_k=top_k,
        limit=limit,
    )
    llm = _build_judge_llm()
    embeddings = _build_ragas_embeddings()

    result = evaluate(
        dataset=dataset,
        metrics=[Faithfulness(), ResponseRelevancy(strictness=1)],
        llm=llm,
        embeddings=embeddings,
        show_progress=True,
        raise_exceptions=False,
    )

    faithfulness_scores = [float(value) for value in result["faithfulness"]]
    response_relevancy_scores = [float(value) for value in result["answer_relevancy"]]

    def _mean_ignore_nan(values: list[Any]) -> float:
        valid_values = [float(value) for value in values if value is not None and not math.isnan(float(value))]
        return sum(valid_values) / len(valid_values) if valid_values else float("nan")

    result_dict = {
        "sample_count": len(dataset),
        "top_k": top_k,
        "faithfulness": _mean_ignore_nan(faithfulness_scores),
        "response_relevancy": _mean_ignore_nan(response_relevancy_scores),
        "faithfulness_scores": faithfulness_scores,
        "response_relevancy_scores": response_relevancy_scores,
        "output_path": str(resolved_output_path),
    }
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(
        json.dumps(result_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result_dict
