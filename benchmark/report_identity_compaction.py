from __future__ import annotations

from typing import Any

IDENTITY_PROJECTION_CONTRACT = "evidence_identity_projection.v1"
IDENTITY_TRACE_LIMITS = {
    "max_candidate_identity_items": 80,
    "max_reranked_identity_items": 30,
}
_LIST_LIMITS = {
    "candidate_evidence": IDENTITY_TRACE_LIMITS["max_candidate_identity_items"],
    "canonical_candidate_evidence": IDENTITY_TRACE_LIMITS[
        "max_candidate_identity_items"
    ],
    "candidate_ranked_evidence": IDENTITY_TRACE_LIMITS["max_candidate_identity_items"],
    "fused_evidence": IDENTITY_TRACE_LIMITS["max_candidate_identity_items"],
    "reranker_input_evidence": IDENTITY_TRACE_LIMITS["max_candidate_identity_items"],
    "reranked_evidence": IDENTITY_TRACE_LIMITS["max_reranked_identity_items"],
    "selected_evidence": IDENTITY_TRACE_LIMITS["max_reranked_identity_items"],
    "generation_context_evidence": IDENTITY_TRACE_LIMITS["max_reranked_identity_items"],
    "used_evidence": IDENTITY_TRACE_LIMITS["max_reranked_identity_items"],
    "execution_operand_evidence": IDENTITY_TRACE_LIMITS["max_reranked_identity_items"],
    "verified_evidence": IDENTITY_TRACE_LIMITS["max_reranked_identity_items"],
    "verified_claim_support_evidence": IDENTITY_TRACE_LIMITS[
        "max_reranked_identity_items"
    ],
    "cited_evidence": IDENTITY_TRACE_LIMITS["max_reranked_identity_items"],
    "emitted_citation_evidence": IDENTITY_TRACE_LIMITS["max_reranked_identity_items"],
}
_IDENTITY_FIELDS = (
    "identity",
    "evidence_id",
    "canonical_id",
    "source_id",
    "runtime_source_id",
    "evaluation_source_id",
    "runtime_identity",
    "evaluation_identity",
    "source_name",
    "source_aliases",
    "document_id",
    "file_id",
    "file_name",
    "page_label",
    "page_number",
    "dataset_page",
    "parser_page_index",
    "page_aliases",
    "element_id",
    "element_type",
    "modality",
    "figure_label",
    "table_label",
    "cell_id",
    "span_id",
    "evidence_level",
    "table_id",
    "parent_element_id",
    "neighbor_element_ids",
    "section_id",
    "row_index",
    "column_index",
    "row_label",
    "column_label",
    "period",
    "period_kind",
    "unit",
    "scale",
    "currency",
    "value",
    "statement_kind",
    "financial_scope",
    "bbox",
    "caption",
    "ocr_text",
    "vlm_text",
    "continuation_id",
    "chunk_start",
    "chunk_end",
    "normalized_text_hash",
    "duplicate_evidence_ids",
    "retrieval_lineage",
    "reranker_input_identity",
    "reranker_score",
    "reranker_rank",
    "reranker_backend",
    "reranker_model",
    "representations",
    "source_backrefs",
    "runtime_source_backrefs",
    "evaluation_source_backrefs",
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
