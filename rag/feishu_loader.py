from dataclasses import dataclass

import requests
from rapidocr_onnxruntime import RapidOCR

from rag.config import settings
from rag.models import SourceElement


BLOCK_TYPE_NAMES = {
    1: "page",
    2: "text",
    3: "heading1",
    4: "heading2",
    5: "heading3",
    6: "heading4",
    7: "heading5",
    8: "heading6",
    9: "heading7",
    10: "heading8",
    11: "heading9",
    12: "bullet",
    13: "ordered",
    14: "code",
    15: "quote",
    16: "callout",
    17: "todo",
    18: "bitable",
    19: "table",
    20: "image",
    21: "file",
    22: "sheet",
    23: "gallery",
    24: "column",
    25: "column_list",
    26: "divider",
    27: "image",
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
    elements: list[SourceElement]
    revision_id: int | None = None
    image_ocr_count: int = 0
    table_count: int = 0
    attachment_count: int = 0


@dataclass(frozen=True)
class FeishuWikiNode:
    """用于递归遍历知识库节点的最小元数据。"""
    space_id: str
    node_token: str
    parent_node_token: str | None
    title: str
    obj_type: str | None
    obj_token: str | None
    has_child: bool
    node_type: str | None = None


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


def _paginate_feishu_json(url: str, token: str, params: dict | None = None) -> list[dict]:
    """拉平飞书分页接口，返回完整的 items 列表。"""
    items: list[dict] = []
    page_token: str | None = None
    base_params = dict(params or {})

    while True:
        request_params = dict(base_params)
        if page_token:
            request_params["page_token"] = page_token
        data = _request_feishu_json(url, token=token, params=request_params)
        items.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
        if not page_token:
            break

    return items


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


def _element_type_for_block(block: dict) -> str:
    block_type_name = _block_type_name(block)
    if block_type_name.startswith("heading"):
        return block_type_name
    if block_type_name in {"bullet", "ordered", "quote", "code", "todo", "table", "image", "file"}:
        return block_type_name
    if block_type_name in {"bitable", "sheet"}:
        return "table"
    return "text"


def _heading_level(element_type: str) -> int | None:
    if not element_type.startswith("heading"):
        return None
    suffix = element_type.removeprefix("heading")
    return int(suffix) if suffix.isdigit() else None


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


# 作用：对内存中的图片字节执行 OCR 识别，返回所有识别到的文本行。
def _ocr_bytes(image_bytes: bytes) -> str:
    result, _ = _get_ocr_engine()(image_bytes)
    if not result:
        return ""

    lines = [item[1] for item in result if len(item) > 1 and item[1]]
    return "\n".join(line.strip() for line in lines if line.strip())


def _ocr_image(file_token: str, token: str) -> str:
    download_url = _fetch_media_download_url(file_token=file_token, token=token)
    image_bytes = _request_feishu_bytes(download_url, token=token)
    return _ocr_bytes(image_bytes)


def _load_document_metadata(doc_id: str, token: str) -> tuple[str, int | None]:
    data = _request_feishu_json(
        f"{settings.feishu.open_api_base}/docx/v1/documents/{doc_id}",
        token=token,
    )
    document = data["document"]
    return document.get("title", doc_id), document.get("revision_id")


def _load_document_blocks(doc_id: str, token: str) -> list[dict]:
    return _paginate_feishu_json(
        f"{settings.feishu.open_api_base}/docx/v1/documents/{doc_id}/blocks",
        token=token,
        params={"page_size": 500},
    )


def list_feishu_wiki_nodes(
    *,
    space_id: str,
    parent_node_token: str | None = None,
    app_id: str | None = None,
    app_secret: str | None = None,
) -> list[FeishuWikiNode]:
    """列出知识库根节点或指定父节点下的直接子节点。"""
    token = get_tenant_access_token(app_id=app_id, app_secret=app_secret)
    params: dict[str, str | int] = {"page_size": 50}
    if parent_node_token:
        params["parent_node_token"] = parent_node_token

    items = _paginate_feishu_json(
        f"{settings.feishu.open_api_base}/wiki/v2/spaces/{space_id}/nodes",
        token=token,
        params=params,
    )
    return [
        FeishuWikiNode(
            space_id=item.get("space_id", space_id),
            node_token=item["node_token"],
            parent_node_token=item.get("parent_node_token"),
            title=item.get("title", ""),
            obj_type=item.get("obj_type"),
            obj_token=item.get("obj_token"),
            has_child=bool(item.get("has_child")),
            node_type=item.get("node_type"),
        )
        for item in items
    ]


def list_feishu_wiki_subtree_docx_nodes(
    *,
    space_id: str,
    parent_node_token: str,
    app_id: str | None = None,
    app_secret: str | None = None,
) -> list[FeishuWikiNode]:
    """递归收集指定知识库父节点下的全部 docx 节点。"""
    token = get_tenant_access_token(app_id=app_id, app_secret=app_secret)
    discovered: list[FeishuWikiNode] = []
    pending = [parent_node_token]
    visited: set[str] = set()

    while pending:
        current_parent = pending.pop()
        if current_parent in visited:
            continue
        visited.add(current_parent)

        # 知识库节点接口一次只返回一层，所以这里通过持续展开子目录来完成递归。
        items = _paginate_feishu_json(
            f"{settings.feishu.open_api_base}/wiki/v2/spaces/{space_id}/nodes",
            token=token,
            params={"page_size": 50, "parent_node_token": current_parent},
        )
        for item in items:
            node = FeishuWikiNode(
                space_id=item.get("space_id", space_id),
                node_token=item["node_token"],
                parent_node_token=item.get("parent_node_token"),
                title=item.get("title", ""),
                obj_type=item.get("obj_type"),
                obj_token=item.get("obj_token"),
                has_child=bool(item.get("has_child")),
                node_type=item.get("node_type"),
            )
            discovered.append(node)
            if node.has_child:
                pending.append(node.node_token)

    deduped: list[FeishuWikiNode] = []
    seen_obj_tokens: set[str] = set()
    for node in discovered:
        if node.obj_type not in ("docx", "file") or not node.obj_token:
            continue
        # 同一篇云文档可能通过多个节点暴露出来，这里按 obj_token 去重，
        # 避免后续重复切片和重复向量化。
        if node.obj_token in seen_obj_tokens:
            continue
        seen_obj_tokens.add(node.obj_token)
        deduped.append(node)
    return deduped


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

    # 先下载图片字节，后续 OCR 和 Gemini caption 共用同一份数据。
    try:
        download_url = _fetch_media_download_url(file_token=file_token, token=token)
        image_bytes = _request_feishu_bytes(download_url, token=token)
    except Exception:
        return f"[图片 {marker}]"

    ocr_text = ""
    try:
        ocr_text = _ocr_bytes(image_bytes)
    except Exception:
        ocr_text = ""

    caption = ""
    caption_error = ""
    try:
        from rag.image_caption import caption_image

        caption = caption_image(image_bytes)
    except Exception as exc:
        caption_error = str(exc)

    parts = [f"[图片 {marker}]"]
    if caption:
        parts.append(f"[图片描述] {caption}")
    elif caption_error:
        # Gemini 调用失败时显式记录原因，方便排查网络/鉴权问题。
        parts.append(f"[图片描述失败: {caption_error}]")
    if ocr_text:
        parts.append(f"[图片文字] {ocr_text}")

    return "\n".join(parts)


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
    elements = [
        SourceElement(
            text=title,
            start=0,
            end=len(title),
            element_type="title",
            title_path=[title],
            metadata={"doc_id": doc_id, "position": 0},
        )
    ]
    image_ocr_count = 0
    table_count = 0
    attachment_count = 0
    current_length = len(title)
    title_path = [title]

    for index, block in enumerate(blocks, start=1):
        rich_text, counters = _extract_rich_block(block, index, token)
        if rich_text:
            element_text = rich_text
            image_ocr_count += counters["image_ocr_count"]
            table_count += counters["table_count"]
            attachment_count += counters["attachment_count"]
        else:
            element_text = _extract_block_text(block)

        if not element_text:
            continue

        element_type = _element_type_for_block(block)
        block_title_path = list(title_path)
        heading_level = _heading_level(element_type)
        if heading_level is not None:
            block_title_path = [title]
            if heading_level > 1:
                block_title_path.extend(title_path[1:heading_level])
            block_title_path.append(element_text)
            title_path = list(block_title_path)

        start = current_length + 1
        end = start + len(element_text)
        lines.append(element_text)
        current_length = end
        elements.append(
            SourceElement(
                text=element_text,
                start=start,
                end=end,
                element_type=element_type,
                title_path=block_title_path,
                metadata={
                    "doc_id": doc_id,
                    "block_id": block.get("block_id"),
                    "block_type": _block_type_name(block),
                    "position": index,
                },
            )
        )

    return FeishuDocument(
        doc_id=doc_id,
        title=title,
        text="\n".join(lines),
        elements=elements,
        revision_id=revision_id,
        image_ocr_count=image_ocr_count,
        table_count=table_count,
        attachment_count=attachment_count,
    )


def load_feishu_file(
    file_token: str,
    *,
    file_name: str = "",
    app_id: str | None = None,
    app_secret: str | None = None,
) -> FeishuDocument:
    """通过飞书 Drive API 下载知识库中导入的外部文件（如 .md），返回 FeishuDocument。"""
    token = get_tenant_access_token(app_id=app_id, app_secret=app_secret)
    file_bytes = _request_feishu_bytes(
        f"{settings.feishu.open_api_base}/drive/v1/files/{file_token}/download",
        token=token,
    )
    text = file_bytes.decode("utf-8")
    title = file_name or file_token
    return FeishuDocument(
        doc_id=file_token,
        title=title,
        text=text,
        elements=[],
    )
