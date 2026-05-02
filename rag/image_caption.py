import base64
import json
import logging
import os
import platform
from threading import Lock

import requests

from rag.config import settings

logger = logging.getLogger(__name__)
_CAPTION_LOCK = Lock()

# 缓存 Windows 系统代理地址，避免每次请求都读注册表。
_windows_proxy_cache: str | None = None
_windows_proxy_checked: bool = False


# 作用：从 Windows 注册表读取系统代理配置，仅在未设置环境变量时兜底。
def _read_windows_system_proxy() -> str | None:
    global _windows_proxy_cache, _windows_proxy_checked
    if _windows_proxy_checked:
        return _windows_proxy_cache
    _windows_proxy_checked = True

    if platform.system() != "Windows":
        return None

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as key:
            proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if not proxy_enable:
                return None
            proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
            if proxy_server:
                _windows_proxy_cache = f"http://{proxy_server}"
                return _windows_proxy_cache
    except OSError:
        pass
    return None


# 作用：构建 requests 库可用的代理字典。
# 优先级：环境变量 HTTPS_PROXY > Windows 系统代理 > 无代理。
def _build_proxies() -> dict | None:
    https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")

    if not https_proxy:
        system_proxy = _read_windows_system_proxy()
        if system_proxy:
            https_proxy = system_proxy
            http_proxy = system_proxy

    proxies = {}
    if https_proxy:
        proxies["https"] = https_proxy
    if http_proxy:
        proxies["http"] = http_proxy
    return proxies or None


# 作用：调用 Gemini 多模态模型为图片生成中文语义描述。
# 图片以 base64 inline_data 直接嵌入请求，无需先上传 File API。
def caption_image(image_bytes: bytes, mime_type: str = "image/png") -> str:
    api_key = settings.gemini.api_key
    if not api_key:
        raise ValueError("Missing Gemini API key.")

    model = settings.gemini.model
    base_url = settings.gemini.base_url

    encoded = base64.b64encode(image_bytes).decode("ascii")
    prompt = (
        "请用一段中文简要描述这张图片的完整内容。"
        "如果是架构图、流程图、时序图：请描述其中包含哪些组件/服务/节点，以及它们之间的调用关系或数据流方向。"
        "如果是 UI 截图或页面：请描述页面功能、关键操作按钮和当前展示的状态信息。"
        "如果是表格：请描述表头结构和关键数据内容。"
        "如果是图表/数据看板：请描述坐标轴含义、数据趋势和关键数值。"
        "如果是普通插图或照片：请描述主题和核心信息。"
        "只输出描述文本，不要加前缀或额外说明。"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": mime_type, "data": encoded}},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 512,
        },
    }

    resp = requests.post(
        f"{base_url}/models/{model}:generateContent?key={api_key}",
        json=payload,
        headers={"Content-Type": "application/json"},
        proxies=_build_proxies(),
        timeout=(10, 60),
    )
    resp.raise_for_status()
    result = resp.json()

    candidates = result.get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        return ""
    return parts[0].get("text", "").strip()
