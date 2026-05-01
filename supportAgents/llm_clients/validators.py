"""按 provider 维护可识别的模型名白名单。"""

VALID_MODELS = {
    "openai": [
        # GPT-5 series (2025)
        "gpt-5.2",
        "gpt-5.1",
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        # GPT-4.1 series (2025)
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        # o-series reasoning models
        "o4-mini",
        "o3",
        "o3-mini",
        "o1",
        "o1-preview",
        # GPT-4o series (legacy but still supported)
        "gpt-4o",
        "gpt-4o-mini",
    ],
    "anthropic": [
        # Claude 4.5 series (2025)
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
        # Claude 4.x series
        "claude-opus-4-1-20250805",
        "claude-sonnet-4-20250514",
        # Claude 3.7 series
        "claude-3-7-sonnet-20250219",
        # Claude 3.5 series (legacy)
        "claude-3-5-haiku-20241022",
        "claude-3-5-sonnet-20241022",
    ],
    "google": [
        # Gemini 3 series (preview)
        "gemini-3-pro-preview",
        "gemini-3-flash-preview",
        # Gemini 2.5 series
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        # Gemini 2.0 series
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ],
    "xai": [
        # Grok 4.1 series
        "grok-4-1-fast",
        "grok-4-1-fast-reasoning",
        "grok-4-1-fast-non-reasoning",
        # Grok 4 series
        "grok-4",
        "grok-4-0709",
        "grok-4-fast-reasoning",
        "grok-4-fast-non-reasoning",
    ],
    "deepseek": [
        # DeepSeek V4 系列（2026-04-24 起官方推荐）
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        # 兼容别名，官方已宣布将在 2026-07-24 下线
        "deepseek-chat",
        "deepseek-reasoner",
    ],
}


def validate_model(provider: str, model: str) -> bool:
    """校验模型名是否属于当前 provider 的已知列表。"""
    provider_lower = provider.lower()

    if provider_lower in ("ollama", "openrouter"):
        return True

    if provider_lower not in VALID_MODELS:
        return True

    return model in VALID_MODELS[provider_lower]
