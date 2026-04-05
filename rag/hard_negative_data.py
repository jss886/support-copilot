from pathlib import Path

from rag.config import RESOURCES_DIR
from rag.ingestion import ingest_directory_to_db


HARD_NEGATIVE_DIR = RESOURCES_DIR / "testdata" / "hard_negative_docs"


HARD_NEGATIVE_SPECS = [
    {
        "file_name": "01_kb_access_legacy.md",
        "title": "知识库接入旧方案与已废弃同步链路",
        "body": [
            "这份材料描述的是早期知识库接入方案，重点放在一次性全量同步，不再推荐用于当前系统。",
            "文中同样会提到知识同步链路、同步成功率、知识工程师和增量水位等词，但结论与现行方案不同。",
            "旧方案建议每日凌晨执行全量导入，不依赖增量同步水位，也不强调在线追踪同步成功率不低于 99.2%。",
            "如果有人搜索知识同步链路不稳定、知识工程师或同步指标，这篇文档在词面上会很像，但它真正讨论的是已废弃流程。",
            "为了故意制造混淆，文中保留了 FS-KB-401、增量同步水位、知识同步成功率等关键词，不过上下文全部在说明为什么旧方案不再适用。",
            "结论部分明确写到：当前版本不要继续沿用这套知识库接入方式，否则会放大延迟和重复入库问题。",
        ],
    },
    {
        "file_name": "02_hybrid_retrieval_obsolete.md",
        "title": "混合检索过渡期策略说明",
        "body": [
            "这篇文档和向量召回、BM25、RRF 融合窗口、Top10 召回率等词高度相关，但它讨论的是过渡期临时策略。",
            "文中提到 RAG-RET-217，也会多次出现混检、重排、融合窗口和检索算法工程师，不过建议与正式方案刻意错开。",
            "过渡期策略主张短时间内关闭 BM25 加权，优先验证纯向量路径的稳定性，因此和正式的混合检索方向不同。",
            "如果评测问题只抓住 RRF 融合窗口或 Top10 召回率，很容易误召回到这篇，因为它也写到了 0.86 这一目标区间。",
            "真正需要区分的是，这里把重点放在灰度期观测，而不是正式检索架构。",
            "结论是：该方案仅用于迁移窗口，不应用于长期检索配置。",
        ],
    },
    {
        "file_name": "03_chunking_old_rules.md",
        "title": "旧版切片参数与紧急兼容规则",
        "body": [
            "文中会反复提到飞书文档切片、chunk 过短、语义连续性和 RAG-CHUNK-318，但它讲的是兼容旧索引的临时参数。",
            "旧规则把 chunk_size 压得更小，目的是让遗留索引快速重建，因此并不适合作为当前推荐方案。",
            "如果用户提到语义连续性、切片命中率提升 12% 或数据平台工程师，这篇文档在表面上都能对上。",
            "但文中实际上强调的是兼容性优先，而不是长期检索质量优先。",
            "为了制造相似语义，本篇也写到了 chunk_overlap、切片边界和命中率指标，不过结论全部偏向迁移兜底。",
            "所以它应被视为高相似干扰文档，而非正确答案来源。",
        ],
    },
    {
        "file_name": "04_duplicate_version_cleanup.md",
        "title": "版本清理失败案例复盘",
        "body": [
            "这篇资料同样围绕版本治理、版本主键、重复来源占比和 RAG-VER-112 展开，但它是在复盘一次失败案例。",
            "失败案例里重复来源占比压到了 5% 以下这个目标并没有达成，反而因为主键设计错误导致旧文档持续污染召回。",
            "如果有人只搜版本主键、重复来源占比或平台架构师，系统可能把它和正式规则文档混起来。",
            "文中也提到了相同的治理术语，不过核心是在解释做错了什么，而不是推荐如何落地。",
            "因此它特别适合拿来做 hard negative，检验检索是否真的理解文档意图。",
            "最终结论是：这套处理方式已下线，不要再复用。",
        ],
    },
    {
        "file_name": "05_ops_template_variant.md",
        "title": "值班团队排障模板补充版",
        "body": [
            "这篇文档会讨论故障排查模板、排障前置条件、SRE 和 OPS-DOC-503，但它面向的是夜班值守手册。",
            "夜班版本刻意省略了大量背景信息，只保留执行步骤和升级路径，因此和正式模板存在明显差异。",
            "当问题里同时出现排障前置条件和定位时长下降 18% 这样的指标时，这篇资料也会显得很相关。",
            "但它重点是紧急处理，而不是知识库里的标准模板设计原则。",
            "文中包含大量相同术语，用来模拟线上库里相似但不完全正确的内容。",
            "如果系统总把这篇排到前面，说明它对模板类问题的判别还不够细。",
        ],
    },
    {
        "file_name": "06_eval_faq_archive.md",
        "title": "历史 FAQ 评测样本归档说明",
        "body": [
            "这篇文档和 FAQ、问法变体、有效样本覆盖 20 个高频主题、EVAL-FAQ-228 高度相关，但它只是历史归档。",
            "归档说明不会告诉你当前如何沉淀评测样本，只会解释过去那批 FAQ 为什么被淘汰。",
            "文中照样会提到客服知识运营、问法扩展和 FAQ 结构，不过这些都是背景，不是现行方法。",
            "如果检索只抓 FAQ、问法变体和高频主题这些词，很容易把它误当成正确文档。",
            "真正正确的文档会讨论如何构建当前评测样本，而不是归档旧数据。",
            "因此它是典型的主题相近、用途不同的干扰项。",
        ],
    },
    {
        "file_name": "07_embedding_cost_tradeoff.md",
        "title": "向量降维实验失败记录",
        "body": [
            "这篇文档同样出现 Embedding、向量维度预算、建库成本下降 25%、EMB-COST-604 和 AI 平台工程师。",
            "但它记录的是一次失败实验：为了省成本把维度压得过低，最终召回质量明显下降。",
            "如果问题只带有向量成本、维度预算或成本下降百分比，它会显得非常像正确答案。",
            "然而文中真正讨论的是负面教训，不是推荐实践。",
            "这类文档非常适合评测模型是否能区分‘成功方案’和‘失败复盘’。",
            "因此我们故意保留相同数字和术语作为干扰锚点。",
        ],
    },
    {
        "file_name": "08_permission_rollback_plan.md",
        "title": "权限回收故障回滚预案",
        "body": [
            "文中会讲权限治理、权限回收任务、AUTH-KB-334 和安全工程师，但主题是权限回收失败后的临时回滚。",
            "它也会提到权限失效生效延迟控制在 10 分钟内，不过是在说明事故期间这个目标没有达成。",
            "如果有人搜索权限回收、延迟生效或安全工程师，很可能误命中到这篇回滚预案。",
            "预案文档强调的是事故处理，不是日常权限治理方案。",
            "因此它与正式权限治理文档共享大量关键词，但结论方向完全不同。",
            "这正好可以拿来制造检索歧义。",
        ],
    },
    {
        "file_name": "09_ocr_cleanup_manual.md",
        "title": "OCR 人工清洗作业单",
        "body": [
            "这篇材料会提到 OCR 清洗、图像文本纠偏、OCR-CLEAN-441 和噪声段落比例低于 8%。",
            "但它面向人工运营同学，主要讲如何手工抽检和修改 OCR 结果，并不描述系统化治理规则。",
            "如果用户只记得图像文本纠偏、噪声比例或信息治理工程师，这篇也会看上去非常像正确文档。",
            "区别在于它只覆盖手工清洗流程，没有讲 RAG 侧的长期策略。",
            "因此它属于高词面相似度、低答案价值的干扰文档。",
            "把它加入知识库后，可以更真实地模拟运营资料与规范文档混杂的场景。",
        ],
    },
    {
        "file_name": "10_multitenant_incident.md",
        "title": "跨租户污染事故复盘",
        "body": [
            "这篇文档和租户隔离、租户过滤标签、TENANT-RAG-714、跨租户误召回次数清零等词高度重合。",
            "但它聚焦的是一次事故复盘，内容主要是时间线、故障影响和补救措施。",
            "如果问题只带跨租户、过滤标签或误召回这些关键词，它可能会抢走正式隔离方案的排名。",
            "复盘文档和设计文档在检索上常常容易混淆，这也是线上最常见的误召回来源之一。",
            "因此我特意保留了同样的指标和角色名，增强对抗性。",
            "正确答案应该是隔离设计，而不是事故复盘。",
        ],
    },
    {
        "file_name": "11_rerank_prompt_notes.md",
        "title": "重排实验提示词备忘录",
        "body": [
            "这篇文档会提到重排、引用窗口长度、RERANK-QUOTE-188 和首屏有效引用率提升 15%。",
            "但它不是正式的重排策略说明，而是一份实验阶段的提示词备忘录。",
            "文中也提到了应用算法工程师、引用片段和首屏效果，不过这些内容非常零散。",
            "如果问题里只保留引用窗口长度或首屏有效引用率，它看起来也可能很相关。",
            "这类备忘录在真实企业知识库里很常见，而且很容易干扰检索排名。",
            "因此把它加入测试库，可以有效检验系统对正式方案和临时笔记的区分能力。",
        ],
    },
    {
        "file_name": "12_monitoring_weekly_note.md",
        "title": "知识库运营周报摘录",
        "body": [
            "这篇周报摘录会出现运营监控、召回健康度、OPS-METRIC-903 和周级异常发现时间缩短 50%。",
            "但周报只是在汇报结果，并不会系统解释如何搭建运营看板与质量监控指标。",
            "如果用户查询召回健康度或监控指标，系统有可能先命中到这种周报型内容。",
            "周报与规范文档共享相同的业务词，却缺乏结构化说明，这种数据在真实知识库里非常常见。",
            "因此它非常适合用作 hard negative，测试模型是否会被报告性材料误导。",
            "真正的目标文档应该是治理设计，而不是结果汇报。",
        ],
    },
]


def generate_hard_negative_docs(output_dir: Path = HARD_NEGATIVE_DIR) -> list[Path]:
    """作用：生成一批与正式知识高度相似但用途不同的干扰文档。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_paths: list[Path] = []

    for spec in HARD_NEGATIVE_SPECS:
        content = "\n\n".join(
            [
                f"# {spec['title']}",
                "## 背景",
                spec["body"][0],
                "## 说明",
                "\n\n".join(spec["body"][1:]),
            ]
        )
        target_path = output_dir / spec["file_name"]
        target_path.write_text(content, encoding="utf-8")
        generated_paths.append(target_path)

    return generated_paths


def seed_hard_negative_docs_to_db(
    *,
    jdbc_url: str | None = None,
    db_user: str | None = None,
    db_password: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    batch_size: int | None = None,
    embedding_dimensions: int = 1536,
    output_dir: Path = HARD_NEGATIVE_DIR,
) -> tuple[int, int]:
    """作用：生成干扰文档并批量切片、向量化后写入 PostgreSQL。"""
    generate_hard_negative_docs(output_dir=output_dir)
    return ingest_directory_to_db(
        source_dir=output_dir,
        jdbc_url=jdbc_url,
        db_user=db_user,
        db_password=db_password,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        batch_size=batch_size,
        embedding_dimensions=embedding_dimensions,
    )
