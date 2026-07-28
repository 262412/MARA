from __future__ import annotations

from typing import Any

from ._runtime_utils import _serialize_value
from .evidence_identity import canonicalize_evidence_item

ATOMIC_ELEMENT_FIELDS = (
    "cell_id",
    "span_id",
    "evidence_level",
    "table_id",
    "parent_element_id",
    "section_id",
    "row_index",
    "column_index",
    "row_label",
    "column_label",
    "period",
    "period_kind",
    "value",
    "unit",
    "scale",
    "currency",
    "statement_kind",
    "financial_scope",
    "continuation_id",
    "chunk_start",
    "chunk_end",
    "normalized_text_hash",
    "figure_label",
    "table_label",
    "ocr_text",
    "vlm_text",
)
ATOMIC_ELEMENT_LIST_FIELDS = (
    "source_aliases",
    "page_aliases",
    "neighbor_element_ids",
    "duplicate_evidence_ids",
    "element_id_aliases",
    "element_type_aliases",
    "retrieval_lineage",
    "representations",
)
ELEMENT_SCORE_FIELDS = (
    "score",
    "dense_score",
    "sparse_score",
    "reranker_score",
    "reranking_score",
    "learned_score",
    "hybrid_fusion_score",
    "element_retriever_score",
    "visual_retriever_score",
    "page_level_score",
)


def element_record_from_mapping(
    value: dict[str, Any],
    *,
    default_file_id: str = "",
    default_file_name: str = "",
    default_page_label: str = "",
    default_element_id: str = "",
    default_modality: str = "element",
    default_evidence_id: str = "",
) -> dict[str, Any] | None:
    metadata = _metadata(value)
    runtime_source_id = _first(value, metadata, "runtime_source_id")
    source_id = _first(value, metadata, "source_id") or runtime_source_id
    file_id = (
        _first(value, metadata, "file_id", "document_id")
        or source_id
        or str(default_file_id or "").strip()
    )
    source_id = source_id or file_id
    page_label = (
        _first(value, metadata, "page_label", "page", "page_number", "dataset_page")
        or str(default_page_label or "").strip()
    )
    element_id = (
        _first(value, metadata, "element_id", "id")
        or str(default_element_id or "").strip()
    )
    cell_id = _first(value, metadata, "cell_id")
    span_id = _first(value, metadata, "span_id")
    if not element_id:
        element_id = _first(value, metadata, "parent_element_id", "table_id")
    if not file_id or not page_label or not (element_id or cell_id or span_id):
        return None

    modality = (
        _first(value, metadata, "modality", "element_type", "type")
        or str(default_modality or "element").strip()
    )
    evidence_id = (
        _first(value, metadata, "evidence_id", "doc_id")
        or str(default_evidence_id or "").strip()
        or f"element:{file_id}:{page_label}:{element_id or cell_id or span_id}"
    )
    output: dict[str, Any] = {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "runtime_source_id": runtime_source_id,
        "file_id": file_id,
        "file_name": (
            _first(value, metadata, "file_name", "source_name")
            or str(default_file_name or "").strip()
        ),
        "page_label": page_label,
        "page_number": _page_number(page_label),
        "element_id": element_id,
        "element_type": modality,
        "modality": modality,
        "bbox": value.get(
            "bbox",
            value.get(
                "box",
                value.get("bounding_box", metadata.get("bbox")),
            ),
        ),
        "caption": _first(value, metadata, "caption"),
        "text": _first(value, metadata, "text", "content"),
        "source_backrefs": _source_backrefs(value, metadata, source_id, page_label),
        "metadata": metadata,
    }
    for field in ATOMIC_ELEMENT_FIELDS:
        field_value = _value(value, metadata, field)
        if field_value not in (None, "", []):
            output[field] = field_value
    for field in ATOMIC_ELEMENT_LIST_FIELDS:
        values = _list_values(_value(value, metadata, field))
        if values:
            output[field] = values
    for field in ELEMENT_SCORE_FIELDS:
        score = _value(value, metadata, field)
        if score not in (None, ""):
            output[field] = score
    scores = _value(value, metadata, "scores")
    if isinstance(scores, dict) and scores:
        output["scores"] = dict(scores)
    if cell_id:
        output["cell_id"] = cell_id
        output.setdefault("evidence_level", "cell")
    elif span_id:
        output["span_id"] = span_id
        output.setdefault("evidence_level", "span")
    else:
        output.setdefault("evidence_level", "element")
    canonical = canonicalize_evidence_item(output)
    record = {
        key: item
        for key, item in canonical.items()
        if item not in ("", [], None) or key in {"bbox", "metadata"}
    }
    return _serialize_value(record)


def _metadata(value: dict[str, Any]) -> dict[str, Any]:
    raw = value.get("metadata")
    return dict(raw) if isinstance(raw, dict) else {}


def _first(
    value: dict[str, Any],
    metadata: dict[str, Any],
    *keys: str,
) -> str:
    for key in keys:
        candidate = _value(value, metadata, key)
        if candidate not in (None, ""):
            return str(candidate).strip()
    return ""


def _value(
    value: dict[str, Any],
    metadata: dict[str, Any],
    key: str,
) -> Any:
    candidate = value.get(key)
    return metadata.get(key) if candidate in (None, "") else candidate


def _list_values(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    values = list(value) if isinstance(value, (list, tuple, set)) else [value]
    output: list[Any] = []
    for item in values:
        if item not in (None, "") and item not in output:
            output.append(item)
    return output


def _source_backrefs(
    value: dict[str, Any],
    metadata: dict[str, Any],
    source_id: str,
    page_label: str,
) -> list[str]:
    refs = [
        str(item).strip()
        for item in (
            *_list_values(value.get("source_backrefs")),
            *_list_values(metadata.get("source_backrefs")),
        )
        if str(item).strip()
    ]
    return list(dict.fromkeys(refs)) or [f"{source_id}#page:{page_label}"]


def _page_number(value: str) -> int | None:
    try:
        numeric = float(str(value).strip())
    except ValueError:
        return None
    return int(numeric) if numeric.is_integer() else None
