import re
from pathlib import Path

from rag.config import DOCS_DIR, PROJECT_ROOT, RESOURCES_DIR
from rag.eval.dataset import save_eval_dataset
from rag.eval.models import EvalItem


DEFAULT_EVAL_DATASET = RESOURCES_DIR / "eval" / "retrieval_eval_set.json"
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^[-*]\s+")
_NUMBER_RE = re.compile(r"^\d+\.\s+")

_FACT_TEMPLATES = [
    "文档里如何描述“{fact}”？",
    "哪里提到了“{fact}”？",
    "我想查“{fact}”相关内容，应该看哪份资料？",
    "关于“{fact}”，知识库里是怎么说明的？",
]

_SECTION_TEMPLATES = [
    "“{section}”这一节主要讲什么？",
    "哪里可以找到关于“{section}”的说明？",
    "知识库里哪篇文档覆盖了“{section}”？",
    "如果要查看“{section}”，应该检索什么文档？",
]

_TITLE_TEMPLATES = [
    "哪篇文档介绍了“{title}”？",
    "我想看“{title}”的内容，应该检索哪份文档？",
]


def _normalize_line(line: str) -> str:
    line = line.strip()
    if not line or line.startswith("```"):
        return ""
    line = _BULLET_RE.sub("", line)
    line = _NUMBER_RE.sub("", line)
    line = line.replace("`", "").strip()
    return line


def _iter_markdown_blocks(doc_path: Path) -> tuple[str, list[tuple[str | None, str]]]:
    title = doc_path.stem
    current_section: str | None = None
    facts: list[tuple[str | None, str]] = []

    for raw_line in doc_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            heading_text = heading_match.group(2).strip()
            if heading_match.group(1) == "#":
                title = heading_text
            else:
                current_section = heading_text
                facts.append((current_section, current_section))
            continue

        normalized = _normalize_line(line)
        if not normalized:
            continue
        if len(normalized) < 6:
            continue
        facts.append((current_section, normalized))

    return title, facts


def _build_items_for_doc(doc_path: Path) -> list[EvalItem]:
    title, facts = _iter_markdown_blocks(doc_path)
    source = str(doc_path.resolve().relative_to(PROJECT_ROOT.resolve()))
    items: list[EvalItem] = []
    seen_questions: set[str] = set()
    fact_index = 0

    for section_title, fact in facts:
        templates = _FACT_TEMPLATES
        for template in templates:
            question = template.format(fact=fact)
            if question in seen_questions:
                continue
            seen_questions.add(question)
            items.append(
                EvalItem(
                    item_id=f"{doc_path.stem}-fact-{fact_index}",
                    question=question,
                    expected_source=source,
                    expected_substrings=[fact],
                    doc_title=title,
                    section_title=section_title,
                )
            )
            fact_index += 1

        if section_title:
            for template in _SECTION_TEMPLATES:
                question = template.format(section=section_title)
                if question in seen_questions:
                    continue
                seen_questions.add(question)
                items.append(
                    EvalItem(
                        item_id=f"{doc_path.stem}-section-{fact_index}",
                        question=question,
                        expected_source=source,
                        expected_substrings=[section_title],
                        doc_title=title,
                        section_title=section_title,
                    )
                )
                fact_index += 1

    for template in _TITLE_TEMPLATES:
        question = template.format(title=title)
        if question in seen_questions:
            continue
        seen_questions.add(question)
        items.append(
            EvalItem(
                item_id=f"{doc_path.stem}-title-{fact_index}",
                question=question,
                expected_source=source,
                expected_substrings=[title],
                doc_title=title,
                section_title=None,
            )
        )
        fact_index += 1

    return items


def generate_eval_dataset(
    source_dir: Path = DOCS_DIR,
    output_path: Path = DEFAULT_EVAL_DATASET,
    target_count: int = 500,
) -> list[EvalItem]:
    source_paths = sorted(path for path in source_dir.glob("*.md") if path.is_file())
    if not source_paths:
        raise ValueError(f"No markdown files found under: {source_dir}")

    all_items: list[EvalItem] = []
    for source_path in source_paths:
        all_items.extend(_build_items_for_doc(source_path))

    if not all_items:
        raise ValueError("Failed to generate any eval items.")

    if len(all_items) < target_count:
        multiplier = (target_count + len(all_items) - 1) // len(all_items)
        expanded: list[EvalItem] = []
        for repeat in range(multiplier):
            for item in all_items:
                expanded.append(
                    EvalItem(
                        item_id=f"{item.item_id}-r{repeat}",
                        question=item.question,
                        expected_source=item.expected_source,
                        expected_substrings=item.expected_substrings,
                        doc_title=item.doc_title,
                        section_title=item.section_title,
                    )
                )
        all_items = expanded

    final_items = all_items[:target_count]
    save_eval_dataset(final_items, output_path)
    return final_items
