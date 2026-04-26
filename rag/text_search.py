import json
import re
from typing import Any

import jieba


_WHITESPACE_RE = re.compile(r"\s+")
_ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9_.:/#-]+")
_LOW_VALUE_QUERY_TOKENS = {
    "我",
    "我们",
    "你",
    "你们",
    "他",
    "她",
    "它",
    "这",
    "这个",
    "这个问题",
    "这块",
    "那",
    "那个",
    "现在",
    "目前",
    "已经",
    "还是",
    "就是",
    "是不是",
    "能不能",
    "可以",
    "应该",
    "怎么",
    "怎么办",
    "怎样",
    "一下",
    "一下子",
    "的话",
    "一下吧",
    "比较",
    "感觉",
    "问题",
    "情况",
    "东西",
    "内容",
    "资料",
    "文档",
    "篇",
    "先",
    "看",
    "哪",
    "哪篇",
    "哪个",
    "哪里",
    "什么",
    "有关",
    "相关",
    "对",
    "上",
    "里",
    "中",
    "和",
    "或",
    "与",
    "及",
    "并",
    "老",
    "总",
}


# 作用：把任意值转成适合参与检索的文本片段，避免 None 或复杂对象直接污染检索文本。
def _stringify_search_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(_stringify_search_value(item) for item in value if item is not None)
    if isinstance(value, dict):
        return " ".join(
            _stringify_search_value(item)
            for item in value.values()
            if item is not None
        )
    return str(value)


# 作用：清洗分词前的原始文本，统一空白字符，避免无意义换行和缩进影响分词结果。
def normalize_search_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


# 作用：对中文文本做检索分词，同时保留接口名、错误码和路径等 ASCII 术语。
def tokenize_for_search(text: str) -> list[str]:
    normalized_text = normalize_search_text(text)
    if not normalized_text:
        return []

    tokens: list[str] = []
    for token in jieba.cut_for_search(normalized_text):
        cleaned = token.strip()
        if not cleaned:
            continue
        if _ASCII_TOKEN_RE.fullmatch(cleaned):
            tokens.append(cleaned.lower())
            continue
        tokens.append(cleaned)
    return tokens


# 作用：把检索分词结果拼成 PostgreSQL FTS 更容易理解的空格文本。
def build_segmented_search_text(text: str) -> str:
    return " ".join(tokenize_for_search(text))


# 作用：从检索分词结果里提取一批更适合落库的关键词，便于后续过滤、诊断和重建 tsv。
def extract_search_keywords(text: str, limit: int = 32) -> list[str]:
    unique_keywords: list[str] = []
    seen: set[str] = set()
    for token in tokenize_for_search(text):
        normalized_token = token.strip()
        if not normalized_token:
            continue
        if len(normalized_token) == 1 and not _ASCII_TOKEN_RE.fullmatch(normalized_token):
            continue
        if normalized_token in seen:
            continue
        seen.add(normalized_token)
        unique_keywords.append(normalized_token)
        if len(unique_keywords) >= limit:
            break
    return unique_keywords


# 作用：从用户查询中提取更适合做关键词召回的高价值词，尽量避开口语噪声导致的过严过滤。
def extract_query_keywords(text: str, limit: int = 12) -> list[str]:
    unique_keywords: list[str] = []
    seen: set[str] = set()
    for token in tokenize_for_search(text):
        normalized_token = token.strip().lower()
        if not normalized_token:
            continue
        if normalized_token in _LOW_VALUE_QUERY_TOKENS:
            continue
        if _ASCII_TOKEN_RE.fullmatch(normalized_token):
            pass
        elif len(normalized_token) < 2:
            continue
        if normalized_token in seen:
            continue
        seen.add(normalized_token)
        unique_keywords.append(normalized_token)
        if len(unique_keywords) >= limit:
            break
    return unique_keywords


# 作用：把文档标题、来源、关键词、标签和切片正文合并成高召回检索文本。
def build_chunk_search_text(
    *,
    title: str,
    source: str,
    content: str,
    keywords: list[str] | None = None,
    tags: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    search_parts = [
        title,
        source,
        _stringify_search_value(keywords or []),
        _stringify_search_value(tags or {}),
        _stringify_search_value(metadata or {}),
        content,
    ]
    merged_text = " ".join(part for part in search_parts if part)
    return build_segmented_search_text(merged_text)


# 作用：把数据库中 jsonb / 文本形式的 tags 统一解析成字典，便于重建检索文本。
def parse_tags(tags: dict[str, Any] | str | None) -> dict[str, Any]:
    if tags is None:
        return {}
    if isinstance(tags, str):
        loaded = json.loads(tags)
        return loaded if isinstance(loaded, dict) else {}
    return tags
