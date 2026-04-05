from pathlib import Path

from rag.config import RESOURCES_DIR
from rag.eval.dataset import save_eval_dataset
from rag.eval.models import EvalItem
from scripts.seed_feishu_kb_docs import TOPIC_SEEDS


DEFAULT_HARD_EVAL_DATASET = RESOURCES_DIR / "eval" / "feishu_kb_seed_eval_set_hard.json"
DEFAULT_HARDER_EVAL_DATASET = (
    RESOURCES_DIR / "eval" / "feishu_kb_seed_eval_set_harder.json"
)


# 作用：把较长的主题名压成更接近日常提问的简称。
PRODUCT_SHORT_NAMES = {
    "知识库接入": "知识库接入",
    "混合检索": "混检",
    "切片策略": "切片",
    "版本治理": "版本治理",
    "文档模板": "文档模板",
    "评测样本": "评测集",
    "向量成本": "向量成本",
    "权限治理": "权限",
    "OCR 清洗": "OCR",
    "租户隔离": "租户隔离",
    "结果重排": "重排",
    "表格入库": "表格入库",
    "答案可信度": "可信度",
    "冷启动": "冷启动",
    "错误码治理": "错误码",
    "评测闭环": "评测闭环",
    "路由分发": "路由",
    "元数据过滤": "元数据过滤",
    "问法扩展": "问法扩展",
    "运营监控": "监控",
}


def _apply_typos(text: str) -> str:
    """作用：构造轻微错别字和口语化写法，模拟真实用户输入。"""
    replacements = {
        "知识": "知试",
        "文档": "文当",
        "错误码": "错码",
        "评测": "评策",
        "向量": "向量",
        "召回": "找回",
        "权限": "权现",
        "方案": "方安",
        "排查": "排cha",
        "指标": "指標",
    }
    typo_text = text
    for source, target in replacements.items():
        if source in typo_text:
            return typo_text.replace(source, target, 1)
    return typo_text


def _neighbor_terms(index: int) -> tuple[str, str]:
    """作用：取相邻主题的关键词，给问题注入跨文档干扰项。"""
    previous_seed = TOPIC_SEEDS[index - 1] if index > 0 else TOPIC_SEEDS[-1]
    next_seed = TOPIC_SEEDS[(index + 1) % len(TOPIC_SEEDS)]
    return previous_seed.keyword, next_seed.keyword


def _build_hard_questions(seed) -> list[tuple[str, list[str]]]:
    """作用：生成更口语化、间接化的困难检索问题。"""
    return [
        (
            f"如果在做{seed.product}时总感觉{seed.core_issue}，我应该先翻哪篇资料？",
            [seed.core_issue],
        ),
        (
            f"哪份文档专门讲“{seed.scenario}”这件事，而且还给了量化目标？",
            [seed.scenario],
        ),
        (
            f"我想找那个提到{seed.metric}的方案，知识库里对应的是哪篇？",
            [seed.metric],
        ),
        (
            f"负责处理“{seed.scenario}”这类事情的{seed.owner_role}，通常会看哪篇说明？",
            [seed.owner_role],
        ),
        (
            f"如果线上暴露出来的问题是{seed.core_issue}，有没有哪份文档明确提过相关治理动作？",
            [seed.core_issue],
        ),
        (
            f"我记得有篇材料谈到{seed.keyword}，但名字忘了，应该搜哪篇？",
            [seed.keyword],
        ),
        (
            f"哪篇知识库文档提到过错误码 {seed.error_code}，而且不是单纯罗列字段？",
            [seed.error_code],
        ),
        (
            f"如果我要排查和{seed.error_code}有关的问题，优先应该命中哪篇资料？",
            [seed.error_code],
        ),
        (
            f"有哪篇文档不是泛泛讲概念，而是直接围绕“{seed.scenario}”展开的？",
            [seed.scenario],
        ),
        (
            f"我在找一篇同时提到了{seed.owner_role}、{seed.metric}和{seed.keyword}的文档，它是哪篇？",
            [seed.keyword, seed.metric],
        ),
    ]


def _build_harder_questions(seed, index: int) -> list[tuple[str, list[str]]]:
    """作用：生成包含错别字、简称和跨主题干扰的更高难度问题。"""
    prev_keyword, next_keyword = _neighbor_terms(index)
    product_short = PRODUCT_SHORT_NAMES.get(seed.product, seed.product)
    typo_issue = _apply_typos(seed.core_issue)
    typo_scenario = _apply_typos(seed.scenario)
    typo_keyword = _apply_typos(seed.keyword)

    return [
        (
            f"{product_short}这块老出问题，我现在更像是碰到了“{typo_issue}”，先看哪篇比较对？",
            [seed.core_issue],
        ),
        (
            f"我想找那个讲{typo_scenario}的文档，不确定是不是跟{prev_keyword}一类，应该命中哪篇？",
            [seed.scenario],
        ),
        (
            f"哪个资料里既提了{seed.metric}，又不是在讲{next_keyword}那一类话题？",
            [seed.metric],
        ),
        (
            f"如果我只记得这篇东西和{seed.owner_role}有关，还提到过{typo_keyword}，应该搜到什么文档？",
            [seed.keyword, seed.owner_role],
        ),
        (
            f"{seed.error_code} 这个错码我在线上看到了，但我想找的是治理思路，不是纯错误码表，哪篇更像？",
            [seed.error_code],
        ),
        (
            f"我在知识库里想找“怎么把{seed.core_issue}压下去”的资料，不想看泛泛介绍，应该是哪篇？",
            [seed.core_issue],
        ),
        (
            f"如果问的是{product_short}相关，但描述里同时出现了{prev_keyword}和{seed.keyword}，更应该命中哪篇？",
            [seed.keyword],
        ),
        (
            f"有篇材料会把{seed.scenario}、{seed.metric}和{seed.owner_role}放在一起讲，我现在只记得这几个点，它是哪篇？",
            [seed.scenario, seed.metric],
        ),
        (
            f"我不是要查术语解释，我要找真正覆盖“{typo_scenario}”落地做法的那份文档，哪篇最对？",
            [seed.scenario],
        ),
        (
            f"哪篇文档更像是在回答“{seed.error_code}出现后该看什么治理资料”，而不是单看错误现象？",
            [seed.error_code],
        ),
        (
            f"如果检索词里有{seed.keyword}，但用户真正想问的是{seed.metric}怎么达成，应该回到哪篇？",
            [seed.metric],
        ),
        (
            f"我想找和{seed.owner_role}有关、同时又明确讲到{seed.core_issue}的资料，不要混到{next_keyword}那篇，应该是哪篇？",
            [seed.owner_role, seed.core_issue],
        ),
    ]


def _build_items(builder, *, suffix: str, dataset_path: Path, code_to_source: dict[str, str]) -> list[EvalItem]:
    """作用：按题目构造函数批量生成 EvalItem 列表。"""
    items: list[EvalItem] = []

    for index, seed in enumerate(TOPIC_SEEDS):
        expected_source = code_to_source.get(seed.code, "")
        for question_index, (question, expected_substrings) in enumerate(builder(seed, index)):
            items.append(
                EvalItem(
                    item_id=f"{seed.code.lower()}-{suffix}-{question_index}",
                    question=question,
                    expected_source=expected_source,
                    expected_substrings=expected_substrings,
                    doc_title=seed.title,
                    section_title=None,
                )
            )

    save_eval_dataset(items, dataset_path)
    return items


def generate_hard_feishu_seed_eval_dataset(
    output_path: Path = DEFAULT_HARD_EVAL_DATASET,
) -> list[EvalItem]:
    """作用：为飞书种子知识库生成一份困难检索评测集。"""
    return _build_items(
        lambda seed, _: _build_hard_questions(seed),
        suffix="hard",
        dataset_path=output_path,
        code_to_source={},
    )


def generate_harder_feishu_seed_eval_dataset(
    output_path: Path = DEFAULT_HARDER_EVAL_DATASET,
) -> list[EvalItem]:
    """作用：为飞书种子知识库生成一份更贴近线上脏查询的评测集。"""
    return _build_items(
        _build_harder_questions,
        suffix="harder",
        dataset_path=output_path,
        code_to_source={},
    )


def _load_code_to_source(manifest_path: Path) -> dict[str, str]:
    """作用：从 manifest 中建立文档编号到飞书来源的映射。"""
    import json

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        item["code"]: item.get("expected_source") or f"feishu://docx/{item['feishu_doc_id']}"
        for item in manifest
        if item.get("code") and (item.get("expected_source") or item.get("feishu_doc_id"))
    }


def rewrite_hard_eval_sources_from_manifest(
    *,
    manifest_path: Path,
    dataset_path: Path = DEFAULT_HARD_EVAL_DATASET,
) -> list[EvalItem]:
    """作用：根据 manifest 回填 hard dataset 的飞书 source。"""
    return _build_items(
        lambda seed, _: _build_hard_questions(seed),
        suffix="hard",
        dataset_path=dataset_path,
        code_to_source=_load_code_to_source(manifest_path),
    )


def rewrite_harder_eval_sources_from_manifest(
    *,
    manifest_path: Path,
    dataset_path: Path = DEFAULT_HARDER_EVAL_DATASET,
) -> list[EvalItem]:
    """作用：根据 manifest 回填 harder dataset 的飞书 source。"""
    return _build_items(
        _build_harder_questions,
        suffix="harder",
        dataset_path=dataset_path,
        code_to_source=_load_code_to_source(manifest_path),
    )
