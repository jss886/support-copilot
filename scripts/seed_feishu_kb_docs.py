import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import requests
from requests import HTTPError

BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_PROJECT_ROOT))

from rag.config import PROJECT_ROOT, RESOURCES_DIR, settings


DEFAULT_SPACE_ID = "7624466364388805839"
DEFAULT_DOC_COUNT = 20
DEFAULT_OUTPUT_DIR = RESOURCES_DIR / "testdata" / "feishu_kb_seed"
DEFAULT_EVAL_PATH = RESOURCES_DIR / "eval" / "feishu_kb_seed_eval_set.json"
REQUEST_TIMEOUT = 30
TEXT_BLOCK = 2
HEADING1_BLOCK = 3
HEADING2_BLOCK = 4


@dataclass(frozen=True)
class TopicSeed:
    index: int
    title: str
    code: str
    product: str
    scenario: str
    core_issue: str
    error_code: str
    metric: str
    keyword: str
    owner_role: str


TOPIC_SEEDS = [
    TopicSeed(1, "RAG 接入飞书知识库的总体方案", "RAG-KB-001", "知识库接入", "将企业内部文档统一接入问答系统", "知识同步链路不稳定", "FS-KB-401", "知识同步成功率不低于 99.2%", "增量同步水位", "知识工程师"),
    TopicSeed(2, "向量召回与 BM25 融合策略说明", "RAG-KB-002", "混合检索", "术语和自然语言问题同时存在", "纯向量召回无法稳定命中精确术语", "RAG-RET-217", "Top10 召回率提升到 0.86 以上", "RRF 融合窗口", "检索算法工程师"),
    TopicSeed(3, "飞书文档切片长度与重叠参数调优", "RAG-KB-003", "切片策略", "长文档跨段落语义容易被切断", "chunk 过短导致上下文缺失", "RAG-CHUNK-318", "平均切片命中率提升 12%", "语义连续性", "数据平台工程师"),
    TopicSeed(4, "知识库多版本文档去重规则", "RAG-KB-004", "版本治理", "同一文档有多个修订版并发存在", "重复内容污染召回排序", "RAG-VER-112", "重复来源占比压缩到 5% 以下", "版本主键", "平台架构师"),
    TopicSeed(5, "故障排查手册的标准化模板", "RAG-KB-005", "文档模板", "运维文档结构不统一", "关键信息埋在自由文本中", "OPS-DOC-503", "问题定位平均时长下降 18%", "排障前置条件", "SRE"),
    TopicSeed(6, "工单 FAQ 沉淀为评测样本的方法", "RAG-KB-006", "评测样本", "历史工单要转成可量化问答", "问题表述与标准答案不一致", "EVAL-FAQ-228", "有效样本覆盖 20 个高频主题", "问法变体", "客服知识运营"),
    TopicSeed(7, "Embedding 维度与成本控制实践", "RAG-KB-007", "向量成本", "索引规模增长过快", "高维向量带来存储和查询压力", "EMB-COST-604", "单次建库成本下降 25%", "向量维度预算", "AI 平台工程师"),
    TopicSeed(8, "飞书知识库权限变更后的回收机制", "RAG-KB-008", "权限治理", "文档访问权限频繁变化", "离职或转岗后遗留文档仍被检索", "AUTH-KB-334", "权限失效生效延迟控制在 10 分钟内", "权限回收任务", "安全工程师"),
    TopicSeed(9, "低质量 OCR 内容的清洗规则", "RAG-KB-009", "OCR 清洗", "截图和扫描件进入知识库", "乱码和错字影响召回与引用", "OCR-CLEAN-441", "噪声段落比例低于 8%", "图像文本纠偏", "信息治理工程师"),
    TopicSeed(10, "多租户支持场景下的知识隔离", "RAG-KB-010", "租户隔离", "不同业务线共用一套 RAG 基座", "召回结果存在跨租户污染风险", "TENANT-RAG-714", "跨租户误召回次数清零", "租户过滤标签", "后端工程师"),
    TopicSeed(11, "检索结果重排与引用片段截断策略", "RAG-KB-011", "结果重排", "命中文档很多但用户只看前几条", "高分片段不一定最适合直接引用", "RERANK-QUOTE-188", "首屏有效引用率提升 15%", "引用窗口长度", "应用算法工程师"),
    TopicSeed(12, "结构化表格内容如何进入知识库", "RAG-KB-012", "表格入库", "制度和配置常以表格形式维护", "表格标题丢失后语义不完整", "TABLE-RAG-526", "表格问答命中率提升到 0.78", "表头继承", "数据产品经理"),
    TopicSeed(13, "客服支持 Copilot 的答案可信度分层", "RAG-KB-013", "答案可信度", "同一问题可能对应多种处理建议", "模型会把低置信信息说得过于确定", "ANS-CONF-355", "低置信回答占比控制在 12% 内", "可信度标签", "客服平台负责人"),
    TopicSeed(14, "知识库冷启动阶段的种子文档建设", "RAG-KB-014", "冷启动", "系统刚上线时缺乏足够语料", "少量文档导致召回偏科严重", "COLDSTART-639", "首周可用问题覆盖率达到 60%", "种子文档优先级", "项目经理"),
    TopicSeed(15, "接口错误码文档的可检索性增强", "RAG-KB-015", "错误码治理", "研发文档里充满接口名和错误码", "自然语言问题难以命中精确码值", "API-ERR-842", "错误码类问题 Top5 命中率提升 20%", "错误码别名", "研发效能工程师"),
    TopicSeed(16, "知识更新后的回灌评测闭环", "RAG-KB-016", "评测闭环", "文档更新后效果变化不可见", "上线后缺少自动化回归验证", "EVAL-LOOP-295", "每次发版都产出召回对比报告", "回归基线集", "测试开发工程师"),
    TopicSeed(17, "多 Agent 支持场景中的检索路由", "RAG-KB-017", "路由分发", "问答、工具调用和流程执行共存", "错误路由会吞掉真实检索需求", "AGENT-ROUTE-467", "检索误路由率低于 3%", "意图裁决阈值", "Agent 平台工程师"),
    TopicSeed(18, "知识片段元数据设计与过滤表达式", "RAG-KB-018", "元数据过滤", "同一篇文档包含多部门共用和专用内容", "过滤维度设计不足导致召回不稳", "META-FILTER-582", "过滤后准确率提升 14%", "标签表达式", "数据治理经理"),
    TopicSeed(19, "召回率量化时的问法多样性建设", "RAG-KB-019", "问法扩展", "用户问法高度口语化", "评测集太标准导致线上效果被高估", "QUERY-VAR-731", "每个事实至少覆盖 4 类问法", "口语化改写", "NLP 工程师"),
    TopicSeed(20, "知识库运营看板与质量监控指标", "RAG-KB-020", "运营监控", "RAG 建成后仍需持续运营", "没有统一指标无法判断知识资产质量", "OPS-METRIC-903", "周级异常发现时间缩短 50%", "召回健康度", "知识库运营经理"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and optionally upload long-form seed documents to a Feishu knowledge base."
    )
    parser.add_argument("--space-id", default=DEFAULT_SPACE_ID, help="Feishu wiki space id.")
    parser.add_argument("--parent-node-token", help="Optional parent wiki node token.")
    parser.add_argument("--doc-count", type=int, default=DEFAULT_DOC_COUNT, help="How many documents to generate.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated markdown files and manifest.",
    )
    parser.add_argument(
        "--eval-output",
        type=Path,
        default=DEFAULT_EVAL_PATH,
        help="Output path for a local retrieval eval dataset.",
    )
    parser.add_argument(
        "--write-feishu",
        action="store_true",
        help="Actually call Feishu OpenAPI. Without this flag the script only generates local files.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.45,
        help="Delay between Feishu write requests to stay under API rate limits.",
    )
    parser.add_argument(
        "--overwrite-local",
        action="store_true",
        help="Overwrite existing local markdown files with the same generated names.",
    )
    return parser.parse_args()


def get_tenant_access_token() -> str:
    if not settings.feishu.app_id or not settings.feishu.app_secret:
        raise ValueError("Missing FEISHU_APP_ID or FEISHU_APP_SECRET.")

    response = requests.post(
        f"{settings.feishu.open_api_base}/auth/v3/tenant_access_token/internal",
        json={
            "app_id": settings.feishu.app_id,
            "app_secret": settings.feishu.app_secret,
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise ValueError(f"Failed to fetch tenant token: {payload.get('msg')}")
    return payload["tenant_access_token"]


def _request_json(
    method: str,
    path: str,
    token: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
) -> dict:
    response = requests.request(
        method,
        f"{settings.feishu.open_api_base}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        params=params,
        json=json_body,
        timeout=REQUEST_TIMEOUT,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise requests.HTTPError(
            f"{exc}. Response body: {response.text}",
            response=response,
        ) from exc
    payload = response.json()
    if payload.get("code") != 0:
        raise ValueError(f"Feishu API request failed: {payload.get('msg') or payload}")
    return payload.get("data", {})


def create_docx_document(title: str, token: str) -> str:
    data = _request_json(
        "POST",
        "/docx/v1/documents",
        token,
        json_body={"title": title, "folder_token": ""},
    )
    document = data["document"]
    return document["document_id"]


def move_doc_to_wiki(
    *,
    space_id: str,
    obj_token: str,
    token: str,
    parent_node_token: str | None = None,
    obj_type: str = "docx",
) -> str | None:
    body = {"obj_type": obj_type, "obj_token": obj_token}
    if parent_node_token:
        body["parent_wiki_token"] = parent_node_token

    data = _request_json(
        "POST",
        f"/wiki/v2/spaces/{space_id}/nodes/move_docs_to_wiki",
        token,
        json_body=body,
    )
    if data.get("wiki_token"):
        return data["wiki_token"]
    if data.get("applied"):
        return None

    task_id = data.get("task_id")
    if not task_id:
        return None

    deadline = time.time() + 120
    while time.time() < deadline:
        task_data = _request_json("GET", f"/wiki/v2/tasks/{task_id}", token)
        task = task_data.get("task", {})
        for result in task.get("move_result", []):
            status = result.get("status")
            status_msg = result.get("status_msg", "")
            if status == 0:
                node = result.get("node", {})
                return node.get("node_token")
            if status == -1:
                raise ValueError(f"Move doc to wiki failed: {status_msg}")
        time.sleep(1.5)

    raise TimeoutError(f"Timed out while waiting for wiki task: {task_id}")


def build_text_block(block_type: int, content: str) -> dict:
    return {
        "block_type": block_type,
        "text": {
            "elements": [
                {
                    "text_run": {
                        "content": content,
                    }
                }
            ]
        },
    }


def _split_long_text(text: str, max_length: int = 900) -> list[str]:
    normalized = text.strip()
    if len(normalized) <= max_length:
        return [normalized]

    chunks: list[str] = []
    remaining = normalized
    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break
        window = remaining[:max_length]
        split_index = max(
            window.rfind("。"),
            window.rfind("；"),
            window.rfind("，"),
            window.rfind("\n"),
        )
        if split_index < max_length // 2:
            split_index = max_length
        chunks.append(remaining[: split_index + 1].strip())
        remaining = remaining[split_index + 1 :].strip()
    return [chunk for chunk in chunks if chunk]


def append_blocks(document_id: str, blocks: list[dict], token: str, sleep_seconds: float) -> None:
    root_block_id = document_id
    for start in range(0, len(blocks), 20):
        batch = blocks[start : start + 20]
        _request_json(
            "POST",
            f"/docx/v1/documents/{document_id}/blocks/{root_block_id}/children",
            token,
            params={"client_token": str(uuid.uuid4())},
            json_body={"index": start, "children": batch},
        )
        time.sleep(sleep_seconds)


def build_markdown_content(seed: TopicSeed) -> str:
    overview = (
        f"{seed.title} 是一篇专门为 RAG 召回率量化准备的长文档，文档编号为 {seed.code}。"
        f"本文围绕 {seed.product} 场景展开，核心目标是解决“{seed.scenario}”时出现的“{seed.core_issue}”问题。"
        f"在实际项目里，团队经常先看到表面症状，再回过头定位真正原因，因此这篇材料刻意保留了背景、指标、流程、角色、例外条件和复盘建议，"
        f"目的是让检索系统在面对长问题、口语化问题、术语问题和错误码问题时都能有稳定的命中机会。文中会多次出现关键短语 {seed.keyword}、"
        f"{seed.error_code}、{seed.metric} 和 {seed.owner_role}，这些都是为了后续构造评测集时能够形成可验证的唯一事实点。"
        f"如果召回系统无法在前几名结果里命中这些事实，就说明知识切片、向量检索、关键词召回或融合排序至少有一环存在短板。"
    )
    symptoms = (
        f"从现网现象来看，{seed.product} 在推进过程中通常会经历三类问题。第一类是显性问题，例如用户反馈问答回答过泛、返回的片段与问题只部分相关，"
        f"或者系统只能命中标题却命不中正文。第二类是隐性问题，例如知识更新后旧切片仍然参与召回，或者不同部门写法不一致导致同一概念被拆成多个表述。"
        f"第三类是治理问题，例如没有人为 {seed.owner_role} 维护统一模板，导致知识库里的资料虽然很多，但真正适合做 RAG 的内容很少。"
        f"这些问题往往不会一次性暴露，而是随着知识规模扩大逐步加剧，所以必须在文档建设初期就把 {seed.keyword} 作为基础治理项。"
    )
    diagnosis = (
        f"针对 {seed.core_issue}，建议把诊断过程拆成四步。第一步确认知识源是否完整，尤其要检查飞书知识库、项目设计文档、排障手册、FAQ 和接口说明是否全部覆盖。"
        f"第二步检查切片策略，重点看长段落是否被错误切断，以及表格、列表、图片 OCR 文本有没有被丢失。第三步检查检索链路，确认向量召回和关键词召回是否各自稳定，"
        f"不要只看最终答案是否看起来合理，而要看中间 TopK 是否真的出现了正确片段。第四步检查评测集质量，确保问题表达包含简称、口语化问法、反问句、错误码和角色描述。"
        f"只有当这四步都完成，{seed.metric} 才有现实可达性，否则所有上线前的“效果不错”都只是主观印象。"
    )
    implementation = (
        f"落地执行时，可以把整套流程固化成标准作业单。先由 {seed.owner_role} 维护文档目录和命名规范，确保标题里出现业务对象、动作和边界条件；"
        f"再由平台工程师把文档切片到统一格式，保留标题路径、来源、更新时间、标签和租户信息；然后在检索阶段引入混合召回，对 {seed.error_code} 这类强结构化术语给出额外加权；"
        f"最后在评测阶段对每个事实生成至少四种问法，包括“文档里如何描述”“哪里提到了”“我想查某个错误码”“哪篇资料覆盖了该主题”。"
        f"这样做的价值不只是把离线分数做高，而是能让系统在真实支持场景中更少出现误引和漏引。"
    )
    controls = (
        f"治理上还需要设置几条强约束。其一，文档正文必须写清前置条件、适用范围、例外条件和回滚方案，不能只给结论不给上下文。其二，所有高频术语都要维护同义词映射，"
        f"例如把内部简称、全称、英文名、历史旧名统一记录在文档里，以免召回系统只能识别一种叫法。其三，监控面板必须持续追踪 {seed.metric}，并单独统计 {seed.error_code} 相关问题的命中情况。"
        f"其四，每次知识更新后都要触发一次回归评测，把历史高频问题跑一遍，观察是否因为新文档引入了排序抖动。没有这些治理动作，再好的 embedding 模型也无法弥补原始知识质量不足。"
    )
    closing = (
        f"最后需要强调，这篇 {seed.code} 文档本身就是为了制造高质量可检索知识样本。它不仅描述了 {seed.product} 的设计原则，也刻意埋入了可以唯一定位的关键事实，"
        f"比如关键词 {seed.keyword}、错误码 {seed.error_code}、角色 {seed.owner_role} 和指标 {seed.metric}。当你后续基于飞书知识库构造 RAG 召回评测时，"
        f"可以直接围绕这些事实生成问题，并验证系统是否能把本篇文档召回到前列。如果结果不理想，就优先回看切片边界、元数据过滤、混合检索参数和评测集问法多样性，"
        f"而不是直接把问题归咎于大模型回答能力。对 RAG 项目而言，知识库建设质量决定了上限，召回链路稳定性决定了下限。"
    )
    return "\n\n".join(
        [
            f"# {seed.title}",
            "## 背景",
            overview,
            "## 现象与风险",
            symptoms,
            "## 诊断步骤",
            diagnosis,
            "## 落地方案",
            implementation,
            "## 治理约束",
            controls,
            "## 评测价值",
            closing,
        ]
    )


def build_doc_blocks(seed: TopicSeed) -> list[dict]:
    markdown = build_markdown_content(seed)
    lines = markdown.splitlines()
    blocks: list[dict] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            title_text = f"标题：{stripped[2:].strip()}"
            for chunk in _split_long_text(title_text):
                blocks.append(build_text_block(TEXT_BLOCK, chunk))
            continue
        if stripped.startswith("## "):
            section_text = f"小节：{stripped[3:].strip()}"
            for chunk in _split_long_text(section_text):
                blocks.append(build_text_block(TEXT_BLOCK, chunk))
            continue
        for chunk in _split_long_text(stripped):
            blocks.append(build_text_block(TEXT_BLOCK, chunk))
    return blocks


def build_eval_items(seed: TopicSeed, expected_source: str) -> list[dict]:
    facts = [
        seed.keyword,
        seed.error_code,
        seed.metric,
        seed.owner_role,
        seed.core_issue,
    ]
    templates = [
        "文档里如何描述“{fact}”？",
        "哪里提到了“{fact}”？",
        "我想查“{fact}”相关内容，应该看哪份资料？",
        "关于“{fact}”，知识库里是怎么说明的？",
    ]
    items: list[dict] = []
    index = 0
    for fact in facts:
        for template in templates:
            items.append(
                {
                    "item_id": f"{seed.code.lower()}-{index}",
                    "question": template.format(fact=fact),
                    "expected_source": expected_source,
                    "expected_substrings": [fact],
                    "doc_title": seed.title,
                    "section_title": None,
                }
            )
            index += 1
    return items


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_local_docs(seeds: list[TopicSeed], output_dir: Path, overwrite: bool) -> list[dict]:
    ensure_output_dir(output_dir)
    manifest: list[dict] = []
    for seed in seeds:
        markdown = build_markdown_content(seed)
        file_name = f"{seed.index:02d}_{seed.code.lower().replace('-', '_')}.md"
        target_path = output_dir / file_name
        if target_path.exists() and not overwrite:
            raise FileExistsError(f"Local file already exists: {target_path}")
        target_path.write_text(markdown, encoding="utf-8")
        manifest.append(
            {
                "seed_index": seed.index,
                "title": seed.title,
                "code": seed.code,
                "word_count": len(markdown.replace("\n", "")),
                "local_path": str(target_path.resolve()),
                "keyword": seed.keyword,
                "error_code": seed.error_code,
                "metric": seed.metric,
                "owner_role": seed.owner_role,
            }
        )
    return manifest


def write_manifest(manifest: list[dict], output_dir: Path) -> Path:
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def write_eval_dataset(items: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    seeds = TOPIC_SEEDS[: args.doc_count]
    if len(seeds) < args.doc_count:
        raise ValueError(f"Only {len(TOPIC_SEEDS)} topic seeds are available.")

    local_manifest = save_local_docs(seeds, args.output_dir, args.overwrite_local)
    eval_items: list[dict] = []
    for seed, item in zip(seeds, local_manifest, strict=True):
        eval_items.extend(build_eval_items(seed, expected_source=item["local_path"]))

    token = None
    if args.write_feishu:
        token = get_tenant_access_token()
        for seed, item in zip(seeds, local_manifest, strict=True):
            title = f"{seed.code} {seed.title}"
            document_id = create_docx_document(title=title, token=token)
            blocks = build_doc_blocks(seed)
            append_blocks(document_id=document_id, blocks=blocks, token=token, sleep_seconds=args.sleep_seconds)
            try:
                wiki_token = move_doc_to_wiki(
                    space_id=args.space_id,
                    obj_token=document_id,
                    token=token,
                    parent_node_token=args.parent_node_token,
                    obj_type="docx",
                )
            except HTTPError as exc:
                message = str(exc)
                if "131006" in message:
                    raise RuntimeError(
                        "The Feishu app can create docx files, but it does not have permission to move them "
                        f"into wiki space {args.space_id}. Add the app as a member/admin of that knowledge space, "
                        "or provide a writable --parent-node-token and re-run the script."
                    ) from exc
                raise
            item["feishu_doc_id"] = document_id
            item["wiki_node_token"] = wiki_token
            item["expected_source"] = f"feishu://docx/{document_id}"
            time.sleep(args.sleep_seconds)

        eval_items = []
        for seed, item in zip(seeds, local_manifest, strict=True):
            eval_items.extend(build_eval_items(seed, expected_source=item["expected_source"]))

    manifest_path = write_manifest(local_manifest, args.output_dir)
    write_eval_dataset(eval_items, args.eval_output)

    print(f"Generated {len(seeds)} documents under: {args.output_dir}")
    print(f"Manifest written to: {manifest_path}")
    print(f"Eval dataset written to: {args.eval_output}")
    if args.write_feishu:
        print(f"Uploaded documents to Feishu wiki space: {args.space_id}")
    else:
        print("Skipped Feishu upload. Re-run with --write-feishu to call OpenAPI.")


if __name__ == "__main__":
    main()
