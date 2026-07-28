from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from .evidence_identity import EvidenceIdentity, identity_of


@dataclass(frozen=True)
class BenchmarkEvidenceRecord:
    identity: EvidenceIdentity
    evidence_id: str = ""
    canonical_id: str = ""
    document_id: str = ""
    source_id: str = ""
    runtime_source_id: str = ""
    source_name: str = ""
    source_aliases: tuple[str, ...] = ()
    page_label: str = ""
    page_index: int | None = None
    dataset_page: str = ""
    parser_page_index: int | None = None
    page_aliases: tuple[str, ...] = ()
    modality: str = ""
    element_id: str = ""
    figure_label: str = ""
    table_label: str = ""
    cell_id: str = ""
    span_id: str = ""
    parent_element_id: str = ""
    neighbor_element_ids: tuple[str, ...] = ()
    section_id: str = ""
    table_id: str = ""
    row_index: int | None = None
    column_index: int | None = None
    row_label: str = ""
    column_label: str = ""
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
    duplicate_evidence_ids: tuple[str, ...] = ()
    evidence_level: str = ""
    element_id_aliases: tuple[str, ...] = ()
    element_type_aliases: tuple[str, ...] = ()
    retrieval_lineage: tuple[dict[str, Any], ...] = ()
    score: Any = None
    bbox: Any = None
    caption: str = ""
    ocr_text: str = ""
    vlm_text: str = ""
    representations: tuple[dict[str, Any], ...] = ()
    section_title: str = ""
    table_title: str = ""
    text: str = ""
    source_backrefs: tuple[str, ...] = ()
    extension_metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["identity"] = self.identity.as_dict()
        for key, value in tuple(payload.items()):
            if isinstance(value, tuple):
                payload[key] = list(value)
        return {
            key: value
            for key, value in payload.items()
            if value not in ("", (), [], {}, None)
        }


def benchmark_evidence_record(item: dict[str, Any]) -> BenchmarkEvidenceRecord:
    metadata = _merged_metadata(item)
    runtime_source_id = _first_text(item, metadata, "runtime_source_id")
    source_id = _first_text(
        item,
        metadata,
        "source_id",
        "file_id",
        "document_id",
        "runtime_source_id",
    )
    page_label = _first_text(
        item,
        metadata,
        "page_label",
        "page",
        "page_number",
        "page_num",
    )
    identity = identity_of(item)
    return BenchmarkEvidenceRecord(
        identity=identity,
        evidence_id=_first_text(item, metadata, "evidence_id", "doc_id"),
        canonical_id=_first_text(item, metadata, "canonical_id") or identity.key,
        document_id=_first_text(item, metadata, "document_id") or source_id,
        source_id=source_id,
        runtime_source_id=runtime_source_id,
        source_name=_first_text(item, metadata, "source_name", "file_name"),
        source_aliases=_first_tuple(item, metadata, "source_aliases"),
        page_label=page_label,
        page_index=_optional_int(item, metadata, "page_index"),
        dataset_page=_first_text(item, metadata, "dataset_page"),
        parser_page_index=_optional_int(item, metadata, "parser_page_index"),
        page_aliases=_first_tuple(item, metadata, "page_aliases"),
        modality=_first_text(item, metadata, "modality", "element_type", "type"),
        element_id=_first_text(item, metadata, "element_id", "element"),
        **_visual_projection(item, metadata),
        cell_id=_first_text(item, metadata, "cell_id"),
        span_id=_first_text(item, metadata, "span_id"),
        parent_element_id=_first_text(item, metadata, "parent_element_id"),
        neighbor_element_ids=_first_tuple(
            item,
            metadata,
            "neighbor_element_ids",
        ),
        section_id=_first_text(item, metadata, "section_id"),
        table_id=_first_text(item, metadata, "table_id"),
        row_index=_optional_int(item, metadata, "row_index"),
        column_index=_optional_int(item, metadata, "column_index"),
        row_label=_first_text(item, metadata, "row_label"),
        column_label=_first_text(item, metadata, "column_label"),
        period=_first_text(item, metadata, "period"),
        period_kind=_first_text(item, metadata, "period_kind"),
        value=_first_text(item, metadata, "value"),
        unit=_first_text(item, metadata, "unit"),
        scale=_first_text(item, metadata, "scale"),
        currency=_first_text(item, metadata, "currency"),
        statement_kind=_first_text(item, metadata, "statement_kind"),
        financial_scope=_first_text(item, metadata, "financial_scope"),
        continuation_id=_first_text(item, metadata, "continuation_id"),
        chunk_start=_optional_int(item, metadata, "chunk_start"),
        chunk_end=_optional_int(item, metadata, "chunk_end"),
        normalized_text_hash=_first_text(item, metadata, "normalized_text_hash"),
        duplicate_evidence_ids=_first_tuple(
            item,
            metadata,
            "duplicate_evidence_ids",
        ),
        evidence_level=_first_text(item, metadata, "evidence_level"),
        element_id_aliases=_first_tuple(item, metadata, "element_id_aliases"),
        element_type_aliases=_first_tuple(item, metadata, "element_type_aliases"),
        retrieval_lineage=_lineage(item, metadata),
        score=item.get("score", metadata.get("score")),
        section_title=_first_text(item, metadata, "section_title"),
        table_title=_first_text(item, metadata, "table_title"),
        text=_first_text(item, metadata, "text", "content", "snippet"),
        source_backrefs=_source_backrefs(item, metadata),
        extension_metadata=_extension_metadata(metadata),
    )


def _visual_projection(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "figure_label": _first_text(item, metadata, "figure_label", "figure_id"),
        "table_label": _first_text(item, metadata, "table_label"),
        "bbox": item.get("bbox", metadata.get("bbox")),
        "caption": _first_text(item, metadata, "caption"),
        "ocr_text": _first_text(item, metadata, "ocr_text"),
        "vlm_text": _first_text(item, metadata, "vlm_text"),
        "representations": _dict_tuple(item, metadata, "representations"),
    }


def _merged_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    nested = metadata.get("metadata")
    if isinstance(nested, dict):
        merged = dict(nested)
        merged.update(metadata)
        return merged
    return metadata


def _first_text(
    item: dict[str, Any],
    metadata: dict[str, Any],
    *keys: str,
) -> str:
    for key in keys:
        value = item.get(key)
        if value in (None, ""):
            value = metadata.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _first_tuple(
    item: dict[str, Any],
    metadata: dict[str, Any],
    key: str,
) -> tuple[str, ...]:
    values = _values(item.get(key)) or _values(metadata.get(key))
    return tuple(
        dict.fromkeys(str(value).strip() for value in values if str(value).strip())
    )


def _optional_int(
    item: dict[str, Any],
    metadata: dict[str, Any],
    key: str,
) -> int | None:
    value = item.get(key)
    if value in (None, ""):
        value = metadata.get(key)
    if value in (None, ""):
        return None
    try:
        numeric = float(str(value))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or not numeric.is_integer():
        return None
    return int(numeric)


def _values(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _lineage(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    value = item.get("retrieval_lineage") or metadata.get("retrieval_lineage") or []
    return tuple(dict(entry) for entry in value if isinstance(entry, dict))


def _dict_tuple(
    item: dict[str, Any],
    metadata: dict[str, Any],
    key: str,
) -> tuple[dict[str, Any], ...]:
    value = item.get(key) or metadata.get(key) or []
    return tuple(dict(entry) for entry in value if isinstance(entry, dict))


def _source_backrefs(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[str, ...]:
    refs: list[str] = []
    for key in ("source_backrefs", "citations", "sources", "source_refs"):
        refs.extend(_values(item.get(key)))
        refs.extend(_values(metadata.get(key)))
    for key in ("citation", "source", "source_ref", "reference"):
        refs.extend(_values(item.get(key)))
        refs.extend(_values(metadata.get(key)))
    return tuple(dict.fromkeys(str(ref).strip() for ref in refs if str(ref).strip()))


_PROJECTED_METADATA_KEYS = {
    "bbox",
    "canonical_id",
    "caption",
    "cell_id",
    "chunk_end",
    "chunk_start",
    "column_index",
    "column_label",
    "continuation_id",
    "currency",
    "dataset_page",
    "doc_id",
    "document_id",
    "duplicate_evidence_ids",
    "element",
    "element_id",
    "element_id_aliases",
    "element_type",
    "element_type_aliases",
    "evidence_id",
    "evidence_level",
    "file_id",
    "file_name",
    "financial_scope",
    "metadata",
    "modality",
    "neighbor_element_ids",
    "normalized_text_hash",
    "ocr_text",
    "page",
    "page_aliases",
    "page_index",
    "page_label",
    "page_num",
    "page_number",
    "parent_element_id",
    "parser_page_index",
    "period",
    "period_kind",
    "representations",
    "retrieval_lineage",
    "row_index",
    "row_label",
    "scale",
    "score",
    "section_id",
    "section_title",
    "source_aliases",
    "source_backrefs",
    "source_id",
    "source_name",
    "span_id",
    "statement_kind",
    "table_id",
    "table_title",
    "text",
    "type",
    "unit",
    "value",
    "vlm_text",
}


def _extension_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in metadata.items()
        if str(key) not in _PROJECTED_METADATA_KEYS
    }
