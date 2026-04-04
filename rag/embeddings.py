import os

from openai import OpenAI

from rag.config import DEFAULT_BASE_URL, DEFAULT_MODEL


class DashScopeEmbeddingClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("Missing DASHSCOPE_API_KEY environment variable.")

        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            encoding_format="float",
        )
        data = response.data
        if len(data) != len(texts):
            raise ValueError(
                f"Embedding count mismatch: expected {len(texts)}, got {len(data)}."
            )
        return [item.embedding for item in data]
