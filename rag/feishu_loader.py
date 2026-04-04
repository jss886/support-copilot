from dataclasses import dataclass

import requests
from rapidocr_onnxruntime import RapidOCR

from rag.config import settings


BLOCK_TYPE_NAMES = {
    1: "page",
    2: "text",
    3: "heading1",
    4: "heading2",
    5: "heading3",
    12: "bullet",
    13: "ordered",
    14: "code",
    15: "quote",
    17: "todo",
    18: "bitable",
    19: "table",
    20: "image",
    21: "file",
    22: "sheet",
}
TOKEN_KEYS = (
    "token",
    "file_token",
    "image_token",
    "attachment_token",
    "media_token",
    "src_token",
)
NAME_KEYS = ("name", "title", "file_name", "display_name")


@dataclass
class FeishuDocument:
    doc_id: str
    title: str
    text: str
    revision_id: int | None = None
    image_ocr_count: int = 0
    table_count: int = 0
    attachment_count: int = 0


_OCR_ENGINE: RapidOCR | None = None


def get_tenant_access_token(
    app_id: str | None = None,
    app_secret: str | None = None,
) -> str:
    resolved_app_id = app_id or settings.feishu.app_id
    resolved_app_secret = app_secret or settings.feishu.app_secret
    if not resolved_app_id or not resolved_app_secret:
        raise ValueError("Missing FEISHU_APP_ID or FEISHU_APP_SECRET.")

    response = requests.post(
        f"{settings.feishu.open_api_base}/auth/v3/tenant_access_token/internal",
        json={
            "app_id": resolved_app_id,
            "app_secret": resolved_app_secret,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise ValueError(
            f"Failed to fetch Feishu tenant access token: {payload.get('msg')}"
        )
    return payload["tenant_access_token"]


def _request_feishu_json(url: str, token: str, params: dict | None = None) -> dict:
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise ValueError(f"Feishu API request failed: {payload.get('msg')}")
    return payload["data"]


def _request_feishu_bytes(url: str, token: str) -> bytes:
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.content


def _collect_text_runs(value: object) -> list[str]:
    if isinstance(value, dict):
        if "text_run" in value:
            content = value["text_run"].get("content", "")
            return [content] if content else []

        texts: list[str] = []
        for child in value.values():
            texts.extend(_collect_text_runs(child))
        return texts

    if isinstance(value, list):
        texts: list[str] = []
        for item in value:
            texts.extend(_collect_text_runs(item))
        return texts

    return []


def _extract_block_text(block: dict) -> str:
    texts = _collect_text_runs(block)
    return "".join(texts).strip()


def _get_ocr_engine() -> RapidOCR:
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def _collect_tokens(value: object) -> list[str]:
    tokens: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in TOKEN_KEYS and isinstance(child, str) and child:
                tokens.append(child)
            else:
                tokens.extend(_collect_tokens(child))
    elif isinstance(value, list):
        for item in value:
            tokens.extend(_collect_tokens(item))
    return tokens


def _find_first_token(block: dict, preferred_keys: tuple[str, ...]) -> str | None:
    for key in preferred_keys:
        value = block.get(key)
        if value is None:
            continue
        tokens = _collect_tokens(value)
        if tokens:
            return tokens[0]

    tokens = _collect_tokens(block)
    return tokens[0] if tokens else None


def _collect_names(value: object) -> list[str]:
    names: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in NAME_KEYS and isinstance(child, str) and child.strip():
                names.append(child.strip())
            else:
                names.extend(_collect_names(child))
    elif isinstance(value, list):
        for item in value:
            names.extend(_collect_names(item))
    return names


def _find_first_name(block: dict, preferred_keys: tuple[str, ...]) -> str | None:
    for key in preferred_keys:
        value = block.get(key)
        if value is None:
            continue
        names = _collect_names(value)
        if names:
            return names[0]

    names = _collect_names(block)
    return names[0] if names else None


def _block_type_name(block: dict) -> str:
    block_type = block.get("block_type")
    return BLOCK_TYPE_NAMES.get(block_type, f"type_{block_type}")


def _block_marker(block: dict, index: int) -> str:
    return (
        f"block_id={block.get('block_id', 'unknown')} "
        f"position={index} "
        f"type={_block_type_name(block)}"
    )


def _fetch_media_download_url(file_token: str, token: str) -> str:
    data = _request_feishu_json(
        f"{settings.feishu.open_api_base}/drive/v1/medias/batch_get_tmp_download_url",
        token=token,
        params={"file_tokens": file_token},
    )
    urls = data.get("tmp_download_urls", [])
    if not urls:
        raise ValueError(f"Failed to get temporary download url for media: {file_token}")

    download_url = urls[0].get("tmp_download_url")
    if not download_url:
        raise ValueError(f"Missing temporary download url for media: {file_token}")
    return download_url


def _ocr_image(file_token: str, token: str) -> str:
    download_url = _fetch_media_download_url(file_token=file_token, token=token)
    image_bytes = _request_feishu_bytes(download_url, token=token)
    result, _ = _get_ocr_engine()(image_bytes)
    if not result:
        return ""

    lines = [item[1] for item in result if len(item) > 1 and item[1]]
    return "\n".join(line.strip() for line in lines if line.strip())


def _load_document_metadata(doc_id: str, token: str) -> tuple[str, int | None]:
    data = _request_feishu_json(
        f"{settings.feishu.open_api_base}/docx/v1/documents/{doc_id}",
        token=token,
    )
    document = data["document"]
    return document.get("title", doc_id), document.get("revision_id")


def _load_document_blocks(doc_id: str, token: str) -> list[dict]:
    items: list[dict] = []
    page_token: str | None = None

    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token

        data = _request_feishu_json(
            f"{settings.feishu.open_api_base}/docx/v1/documents/{doc_id}/blocks",
            token=token,
            params=params,
        )
        items.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
        if not page_token:
            break

    return items


def _extract_table_block(block: dict, index: int) -> str:
    text = _extract_block_text(block)
    marker = _block_marker(block, index)
    if text:
        return f"[表格 {marker}]\n{text}"
    return f"[表格 {marker}]"


def _extract_attachment_block(block: dict, index: int, token: str) -> str:
    marker = _block_marker(block, index)
    name = _find_first_name(block, ("file", "attachment", "attachments", "sheet"))
    file_token = _find_first_token(block, ("file", "attachment", "attachments", "sheet"))

    parts = [f"[附件 {marker}]"]
    if name:
        parts.append(f"名称: {name}")

    ocr_text = ""
    if file_token:
        try:
            ocr_text = _ocr_image(file_token=file_token, token=token)
        except Exception:
            ocr_text = ""

    if ocr_text:
        parts.append("[附件OCR]")
        parts.append(ocr_text)

    return "\n".join(parts)


def _extract_image_block(block: dict, index: int, token: str) -> str:
    marker = _block_marker(block, index)
    file_token = _find_first_token(block, ("image",))
    if not file_token:
        return f"[图片 {marker}]"

    try:
        ocr_text = _ocr_image(file_token=file_token, token=token)
    except Exception:
        ocr_text = ""

    if not ocr_text:
        return f"[图片 {marker}]"
    return f"[图片OCR {marker}]\n{ocr_text}"


def _extract_rich_block(
    block: dict,
    index: int,
    token: str,
) -> tuple[str | None, dict[str, int]]:
    counters = {"image_ocr_count": 0, "table_count": 0, "attachment_count": 0}

    image_token = _find_first_token(block, ("image",))
    if image_token:
        counters["image_ocr_count"] = 1
        return _extract_image_block(block, index, token), counters

    if any(key in block for key in ("table", "sheet", "bitable")):
        counters["table_count"] = 1
        return _extract_table_block(block, index), counters

    if any(key in block for key in ("file", "attachment", "attachments")):
        counters["attachment_count"] = 1
        return _extract_attachment_block(block, index, token), counters

    return None, counters


def load_feishu_document(
    doc_id: str,
    app_id: str | None = None,
    app_secret: str | None = None,
) -> FeishuDocument:
    token = get_tenant_access_token(app_id=app_id, app_secret=app_secret)
    title, revision_id = _load_document_metadata(doc_id, token)
    blocks = _load_document_blocks(doc_id, token)

    lines = [title]
    image_ocr_count = 0
    table_count = 0
    attachment_count = 0

    for index, block in enumerate(blocks, start=1):
        rich_text, counters = _extract_rich_block(block, index, token)
        if rich_text:
            lines.append(rich_text)
            image_ocr_count += counters["image_ocr_count"]
            table_count += counters["table_count"]
            attachment_count += counters["attachment_count"]
            continue

        text = _extract_block_text(block)
        if text:
            lines.append(text)
            continue

    return FeishuDocument(
        doc_id=doc_id,
        title=title,
        text="\n".join(lines),
        revision_id=revision_id,
        image_ocr_count=image_ocr_count,
        table_count=table_count,
        attachment_count=attachment_count,
    )
