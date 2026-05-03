import os
from typing import Any, Literal, Optional

from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI

from .base_client import BaseLLMClient
from .validators import validate_model


class DeepSeekChatOpenAI(ChatOpenAI):
    """对 DeepSeek 特殊参数做兼容处理的聊天模型封装。

    额外处理：
    - reasoning_content 的保留与回传（DeepSeek thinking 模式要求回传该字段）
    - deepseek-reasoner 模型的采样参数剔除
    """

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

    # 作用：从 API 原始响应中提取 reasoning_content，注入到 AIMessage.additional_kwargs 中，
    # 避免 LangChain 的 _convert_dict_to_message 丢弃该字段。
    def _create_chat_result(
        self,
        response: dict | Any,
        generation_info: dict | None = None,
    ) -> Any:
        chat_result = super()._create_chat_result(response, generation_info)
        # 从原始响应里取出 reasoning_content，补到 AIMessage 上
        response_dict = response if isinstance(response, dict) else response.model_dump()
        choices = response_dict.get("choices") or []
        for i, res in enumerate(choices):
            msg = res.get("message") or {}
            reasoning = msg.get("reasoning_content", "")
            if reasoning and i < len(chat_result.generations):
                gen = chat_result.generations[i]
                if isinstance(gen.message, AIMessage):
                    gen.message.additional_kwargs["reasoning_content"] = reasoning
        return chat_result

    # 作用：在构建请求时，把 AIMessage.additional_kwargs 中的 reasoning_content 回传到消息
    # dict 中，满足 DeepSeek API "thinking 模式下必须回传 reasoning_content" 的要求。
    def _get_request_payload(
        self,
        input_: Any,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        messages = self._convert_input(input_).to_messages()
        msg_dicts = payload.get("messages") or []
        if len(msg_dicts) != len(messages):
            return payload
        for orig_msg, msg_dict in zip(messages, msg_dicts):
            if isinstance(orig_msg, AIMessage):
                reasoning = orig_msg.additional_kwargs.get("reasoning_content", "")
                if reasoning:
                    msg_dict["reasoning_content"] = reasoning
        return payload


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
