import asyncio
import json
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
from ragas.metrics.collections import ContextRecall

from rag.answering import answer_question_from_context
from rag.embeddings import DashScopeEmbeddingClient
from rag.eval.dataset import load_eval_dataset
from rag.eval.models import EvalItem
from rag.retrieval import retrieve


DEFAULT_RAGAS_OUTPUT = Path("resources/eval/ragas_eval_result.json")


class DashScopeRagasEmbeddings(BaseRagasEmbeddings):
    """作用：把项目现有的 DashScope embedding 客户端适配成 RAGAS 需要的接口。"""

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


# 作用：读取必需的环境变量，缺失时直接报错，避免评测跑到中途才失败。
def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


# 作用：构造用于 RAGAS 评测的 DeepSeek judge 模型。
def _build_judge_llm() -> LangchainLLMWrapper:
    model = ChatOpenAI(
        model="deepseek-chat",
        api_key=_require_env("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1",
        temperature=0,
        n=1,
    )
    return LangchainLLMWrapper(model)


# 作用：构造 RAGAS 需要的 embedding 包装器。
def _build_ragas_embeddings() -> DashScopeRagasEmbeddings:
    _require_env("DASHSCOPE_API_KEY")
    return DashScopeRagasEmbeddings()


# 作用：忽略 RAGAS 结果中的空值和 NaN，统一计算聚合均值。
def _mean_ignore_nan(values: list[Any]) -> float:
    valid_values = [float(value) for value in values if value is not None and not math.isnan(float(value))]
    return sum(valid_values) / len(valid_values) if valid_values else float("nan")


# 作用：把当前项目的问答链路转换成 RAGAS 可消费的单条样本。
def _build_single_turn_sample(item: EvalItem, top_k: int) -> dict[str, Any]:
    retrieved = retrieve(query=item.question, top_k=top_k)
    retrieved_contexts = [record.text for _, record in retrieved]

    # 这里直接复用已检索结果生成答案，避免评测阶段对同一问题重复跑一次检索链路。
    response = answer_question_from_context(question=item.question, retrieved=retrieved)
    return {
        "user_input": item.question,
        "retrieved_contexts": retrieved_contexts,
        "response": response,
        "reference": "\n".join(item.expected_substrings),
    }


# 作用：兼容目录或文件路径输入，统一解析成可写的结果文件路径。
def resolve_ragas_output_path(output_path: Path) -> Path:
    if output_path.exists() and output_path.is_dir():
        return output_path / DEFAULT_RAGAS_OUTPUT.name
    if output_path.suffix:
        return output_path
    return output_path / DEFAULT_RAGAS_OUTPUT.name


# 作用：从现有检索评测集构造成 RAGAS 可直接消费的数据集。
def build_ragas_dataset(
    *,
    dataset_path: Path,
    top_k: int = 5,
    limit: int | None = None,
) -> Dataset:
    items = load_eval_dataset(dataset_path)
    if limit is not None:
        items = items[:limit]

    rows = [_build_single_turn_sample(item, top_k=top_k) for item in items]
    return Dataset.from_list(rows)


# 作用：构造 RAGAS 评估指标，并显式注入模型依赖，兼容当前安装版本的构造参数要求。
def _build_ragas_metrics(
    *,
    llm: LangchainLLMWrapper,
    embeddings: BaseRagasEmbeddings,
) -> list[Any]:
    return [
        Faithfulness(llm=llm),
        ResponseRelevancy(llm=llm, embeddings=embeddings, strictness=1),
        ContextRecall(llm=llm),
    ]


# 作用：执行 RAGAS 三项核心指标评测，并把结果落盘。
def evaluate_ragas_metrics(
    *,
    dataset_path: Path,
    top_k: int = 5,
    limit: int | None = None,
    output_path: Path = DEFAULT_RAGAS_OUTPUT,
) -> dict[str, Any]:
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
        metrics=_build_ragas_metrics(llm=llm, embeddings=embeddings),
        llm=llm,
        embeddings=embeddings,
        show_progress=True,
        raise_exceptions=False,
    )

    faithfulness_scores = [float(value) for value in result["faithfulness"]]
    response_relevancy_scores = [float(value) for value in result["answer_relevancy"]]
    context_recall_scores = [float(value) for value in result["context_recall"]]

    result_dict = {
        "dataset_path": str(dataset_path.resolve()),
        "sample_count": len(dataset),
        "top_k": top_k,
        "faithfulness": _mean_ignore_nan(faithfulness_scores),
        "response_relevancy": _mean_ignore_nan(response_relevancy_scores),
        "context_recall": _mean_ignore_nan(context_recall_scores),
        "faithfulness_scores": faithfulness_scores,
        "response_relevancy_scores": response_relevancy_scores,
        "context_recall_scores": context_recall_scores,
        "output_path": str(resolved_output_path),
    }
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(
        json.dumps(result_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result_dict
