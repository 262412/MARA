from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceElement:
    evidence_id: str
    source_id: str = ""
    runtime_source_id: str = ""
    evaluation_source_id: str = ""
    runtime_identity: str = ""
    evaluation_identity: str = ""
    source_name: str = ""
    source_aliases: list[str] = field(default_factory=list)
    page_label: str = ""
    dataset_page: str = ""
    parser_page_index: int | None = None
    page_aliases: list[str] = field(default_factory=list)
    modality: str = "text"
    element_id: str = ""
    figure_label: str = ""
    table_label: str = ""
    cell_id: str = ""
    span_id: str = ""
    canonical_id: str = ""
    parent_element_id: str = ""
    neighbor_element_ids: list[str] = field(default_factory=list)
    section_id: str = ""
    table_id: str = ""
    table_instance_id: str = ""
    table_group_id: str = ""
    block_id: str = ""
    cell_role: str = ""
    materialization_source_id: str = ""
    row_index: int | None = None
    column_index: int | None = None
    row_label: str = ""
    column_label: str = ""
    raw_row_label: str = ""
    raw_column_label: str = ""
    normalized_row_label: str = ""
    normalized_column_label: str = ""
    period: str = ""
    period_kind: str = ""
    value: str = ""
    unit: str = ""
    scale: str = ""
    currency: str = ""
    statement_kind: str = ""
    financial_scope: str = ""
    continuation_id: str = ""
    chunk_start: int | None = None
    chunk_end: int | None = None
    normalized_text_hash: str = ""
    duplicate_evidence_ids: list[str] = field(default_factory=list)
    retrieval_lineage: list[dict[str, Any]] = field(default_factory=list)
    bbox: Any = None
    caption: str = ""
    text: str = ""
    ocr_text: str = ""
    vlm_text: str = ""
    representations: list[dict[str, Any]] = field(default_factory=list)
    source_backrefs: list[str] = field(default_factory=list)
    runtime_source_backrefs: list[str] = field(default_factory=list)
    evaluation_source_backrefs: list[str] = field(default_factory=list)
    evidence_level: str = "page"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for field_name in (
            "source_aliases",
            "runtime_source_id",
            "evaluation_source_id",
            "runtime_identity",
            "evaluation_identity",
            "dataset_page",
            "parser_page_index",
            "page_aliases",
            "cell_id",
            "span_id",
            "figure_label",
            "table_label",
            "table_instance_id",
            "table_group_id",
            "block_id",
            "cell_role",
            "materialization_source_id",
            "row_label",
            "column_label",
            "raw_row_label",
            "raw_column_label",
            "normalized_row_label",
            "normalized_column_label",
            "period",
            "period_kind",
            "value",
            "unit",
            "scale",
            "currency",
            "statement_kind",
            "financial_scope",
            "representations",
            "evaluation_source_backrefs",
            "runtime_source_backrefs",
        ):
            if payload[field_name] in ("", None, []):
                payload.pop(field_name)
        return payload


@dataclass(frozen=True)
class EvidenceBundle:
    route: str
    items: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
