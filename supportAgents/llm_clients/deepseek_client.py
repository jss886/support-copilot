import os
from typing import Any, Optional

from langchain_openai import ChatOpenAI

from .base_client import BaseLLMClient
from .validators import validate_model


class DeepSeekChatOpenAI(ChatOpenAI):
    """对 DeepSeek 特殊参数做兼容处理的聊天模型封装。"""

    def __init__(self, **kwargs):
        extra_body = dict(kwargs.get("extra_body") or {})
        thinking = extra_body.get("thinking")
        model = str(kwargs.get("model", "")).lower()
        is_thinking_enabled = model == "deepseek-reasoner" or bool(thinking)

        # 作用：DeepSeek 思考模式下这些采样参数不会生效，提前剔除避免上层误解。
        if is_thinking_enabled:
            kwargs.pop("temperature", None)
            kwargs.pop("top_p", None)

        if extra_body:
            kwargs["extra_body"] = extra_body
        super().__init__(**kwargs)


class DeepSeekClient(BaseLLMClient):
    """DeepSeek 模型客户端，走官方 OpenAI 兼容接口。"""

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(model, base_url, **kwargs)

    # 作用：构造 DeepSeek 聊天模型实例，统一注入官方默认地址、鉴权和可选思考模式。
    def get_llm(self) -> Any:
        llm_kwargs = {
            "model": self.model,
            "base_url": self.base_url or "https://api.deepseek.com",
        }

        api_key = self.kwargs.get("api_key") or os.environ.get("DEEPSEEK_API_KEY")
        if api_key:
            llm_kwargs["api_key"] = api_key

        for key in (
            "timeout",
            "max_retries",
            "callbacks",
            "max_tokens",
            "temperature",
            "top_p",
        ):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        # 作用：最新官方接口要求把 thinking 放在 extra_body 里，这里统一做兼容封装。
        if self.kwargs.get("thinking"):
            llm_kwargs["extra_body"] = {"thinking": self.kwargs["thinking"]}

        return DeepSeekChatOpenAI(**llm_kwargs)

    # 作用：校验当前模型名是否属于已知的 DeepSeek 官方模型或兼容别名。
    def validate_model(self) -> bool:
        return validate_model("deepseek", self.model)
