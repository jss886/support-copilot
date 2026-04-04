import os

from openai import OpenAI

from rag.config import settings


class DashScopeEmbeddingClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
        dimensions: int | None = None,
    ) -> None:
        self.api_key = api_key or settings.dashscope.api_key
        if not self.api_key:
            raise ValueError("Missing DASHSCOPE_API_KEY environment variable.")

        self.model = model or settings.dashscope.model
        self.base_url = (base_url or settings.dashscope.base_url).rstrip("/")
        self.timeout = timeout or settings.dashscope.timeout
        self.dimensions = (
            dimensions
            if dimensions is not None
            else settings.dashscope.default_dimensions
        )
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        request_kwargs = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float",
        }
        if self.dimensions is not None:
            request_kwargs["dimensions"] = self.dimensions

        response = self.client.embeddings.create(**request_kwargs)
        data = response.data
        if len(data) != len(texts):
            raise ValueError(
                f"Embedding count mismatch: expected {len(texts)}, got {len(data)}."
            )
        return [item.embedding for item in data]
