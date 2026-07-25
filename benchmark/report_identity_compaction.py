from __future__ import annotations

from typing import Any

IDENTITY_PROJECTION_CONTRACT = "evidence_identity_projection.v1"
IDENTITY_TRACE_LIMITS = {
    "max_candidate_identity_items": 80,
    "max_reranked_identity_items": 30,
}
_LIST_LIMITS = {
    "candidate_evidence": IDENTITY_TRACE_LIMITS["max_candidate_identity_items"],
    "reranked_evidence": IDENTITY_TRACE_LIMITS["max_reranked_identity_items"],
}
_IDENTITY_FIELDS = (
    "evidence_id",
    "canonical_id",
    "source_id",
    "source_name",
    "source_aliases",
    "document_id",
    "file_id",
    "file_name",
    "page_label",
    "dataset_page",
    "parser_page_index",
    "page_aliases",
    "element_id",
    "cell_id",
    "table_id",
    "row_index",
    "column_index",
    "row_label",
    "column_label",
    "period",
    "unit",
    "scale",
    "currency",
    "continuation_id",
    "normalized_text_hash",
    "duplicate_evidence_ids",
    "source_backrefs",
)


def compact_identity_evidence_list(
    values: list[Any],
    key: str,
) -> list[dict[str, Any]] | None:
    limit = _LIST_LIMITS.get(key)
    if limit is None:
        return None
    return [
        _identity_projection(item) for item in values[:limit] if isinstance(item, dict)
    ]


def is_identity_only_projection(items: list[dict[str, Any]]) -> bool:
    return bool(items) and all(
        item.get("identity_projection") == IDENTITY_PROJECTION_CONTRACT
        for item in items
    )


def _identity_projection(item: dict[str, Any]) -> dict[str, Any]:
    output = {
        field: item[field]
        for field in _IDENTITY_FIELDS
        if field in item and item[field] not in ("", None, [])
    }
    output["identity_projection"] = IDENTITY_PROJECTION_CONTRACT
    return output
