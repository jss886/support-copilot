from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EvalItem:
    item_id: str
    question: str
    expected_source: str
    expected_substrings: list[str]
    doc_title: str
    section_title: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
