from __future__ import annotations

from typing import Any

from .evidence_alias_lookup import unambiguous_evidence_alias_lookup
from .evidence_identity import identity_of
from .financial_table import parse_financial_table_cells


def calculation_evidence_lookup(
    items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return unambiguous_evidence_alias_lookup(calculation_evidence_items(items))


def calculation_evidence_items(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    identities: set[str] = set()
    for item in items:
        candidates = [
            item,
            *(
                materialize_financial_cell(item, cell)
                for cell in parse_financial_table_cells(item)
            ),
        ]
        for candidate in candidates:
            identity = identity_of(candidate).key
            if identity in identities:
                continue
            identities.add(identity)
            expanded.append(candidate)
    return expanded


def materialize_financial_cell(item: dict[str, Any], cell: Any) -> dict[str, Any]:
    materialized = dict(item)
    materialized.pop("identity", None)
    materialized.pop("canonical_id", None)
    for key in (
        "reranker_backend",
        "reranker_input_identity",
        "reranker_model",
        "reranker_observations",
        "reranker_rank",
        "reranker_score",
        "reranking_score",
    ):
        materialized.pop(key, None)
    parent_evidence_id = str(
        item.get("evidence_id")
        or item.get("canonical_id")
        or item.get("element_id")
        or ""
    ).strip()
    materialized.update(
        {
            "evidence_id": cell.cell_id,
            "cell_id": cell.cell_id,
            "cell_role": cell.cell_role,
            "evidence_level": "cell",
            "table_id": cell.table_id,
            "table_instance_id": cell.table_instance_id,
            "table_group_id": cell.table_group_id,
            "block_id": cell.block_id,
            "physical_cell_identity": cell.physical_identity.as_dict(),
            "semantic_cell_key": cell.semantic_key.as_dict(),
            "parent_element_id": cell.table_id,
            "materialization_source_id": parent_evidence_id,
            "row_index": cell.row_index,
            "column_index": cell.column_index,
            "row_label": cell.row_label,
            "column_label": cell.column_label,
            "period": cell.period,
            "period_kind": cell.period_kind,
            "value": str(cell.value),
            "unit": cell.unit,
            "scale": cell.scale,
            "currency": cell.currency,
            "statement_kind": cell.statement_kind,
            "financial_scope": cell.financial_scope,
            "text": cell.verification_text(),
            "caption": cell.row_label,
            "ocr_text": "",
            "vlm_text": "",
            "representations": [],
        }
    )
    metadata = dict(materialized.get("metadata") or {})
    for key in (
        "late_interaction_tokens",
        "representations",
        "caption",
        "ocr_text",
        "vlm_text",
        "reranker_backend",
        "reranker_execution_trace",
        "reranker_execution_traces",
        "reranker_input_identity",
        "reranker_model",
        "reranker_observations",
        "reranker_rank",
        "reranker_score",
        "reranking_score",
    ):
        metadata.pop(key, None)
    materialized["metadata"] = metadata
    materialized["canonical_id"] = identity_of(materialized).key
    return materialized


def calculation_operand_identity(item: dict[str, Any], operand: Any) -> str:
    if operand.cell_id:
        return cell_identity(item, operand.cell_id)
    return identity_of(item).key


def cell_identity(item: dict[str, Any], cell_id: str) -> str:
    payload = dict(item)
    payload.pop("identity", None)
    payload.pop("canonical_id", None)
    payload["cell_id"] = cell_id
    payload["evidence_level"] = "cell"
    return identity_of(payload).key


def same_source(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_source = _source_id(left)
    right_source = _source_id(right)
    return bool(left_source and left_source == right_source)


def _source_id(item: dict[str, Any]) -> str:
    metadata = dict(item.get("metadata") or {})
    return str(
        item.get("source_id")
        or item.get("file_id")
        or item.get("document_id")
        or metadata.get("source_id")
        or ""
    ).strip()
