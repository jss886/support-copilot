from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ExpectedEvidence:
    # 作用：描述单条评测样本期望命中的目标证据，按数据库主键做精确匹配。
    db_chunk_id: str
    source: str


@dataclass(frozen=True)
class EvalItem:
    # 作用：统一定义检索与回答评测样本，新结构优先，旧字段仅用于兼容历史脚本。
    item_id: str
    question: str
    expected_evidences: list[ExpectedEvidence] = field(default_factory=list)
    ground_truth: str = ""
    doc_title: str = ""
    section_title: str | None = None
    expected_source: str = ""
    expected_substrings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
