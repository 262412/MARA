from __future__ import annotations

from typing import Any

from .evidence_alias_lookup import unambiguous_evidence_alias_lookup
from .evidence_identity import identity_of
from .financial_statement_identity import source_identity
from .financial_table import parse_financial_table_cells_with_context

_RUNTIME_IDENTITY_FIELDS = (
    "evaluation_identity",
    "reranker_backend",
    "reranker_input_identity",
    "reranker_model",
    "reranker_observations",
    "reranker_rank",
    "reranker_score",
    "reranking_score",
    "runtime_identity",
)
_TRANSIENT_METADATA_FIELDS = (
    "evaluation_identity",
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
    "runtime_identity",
)


def calculation_evidence_lookup(
    items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return unambiguous_evidence_alias_lookup(calculation_evidence_items(items))


def calculation_evidence_items(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    identities: set[str] = set()
    for item in reconcile_materialized_cells(items):
        candidates = [
            item,
            *(
                materialize_financial_cell(item, cell)
                for cell in parse_financial_table_cells_with_context(item, items)
            ),
        ]
        for candidate in candidates:
            identity = identity_of(candidate).key
            if identity in identities:
                continue
            identities.add(identity)
            expanded.append(candidate)
    return expanded


def reconcile_materialized_cells(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    child_parent_ids = {
        parent_id for item in items if (parent_id := _structured_child_parent_id(item))
    }
    if not child_parent_ids:
        return items
    available_parent_aliases = set().union(
        *(
            _parent_aliases(item)
            for item in items
            if _parent_aliases(item) & child_parent_ids
        ),
        set(),
    )
    if not available_parent_aliases:
        return items
    reconciled: list[dict[str, Any]] = []
    for item in items:
        parent_id = _structured_child_parent_id(item)
        if parent_id and parent_id in available_parent_aliases:
            continue
        reconciled.append(item)
        if _parent_aliases(item) & child_parent_ids:
            reconciled.extend(
                materialize_financial_cell(item, cell)
                for cell in parse_financial_table_cells_with_context(item, items)
            )
    return reconciled


def _structured_child_parent_id(item: dict[str, Any]) -> str:
    if str(item.get("evidence_level") or "").strip().lower() != "cell":
        return ""
    if not int(item.get("row_index") or 0) or not int(item.get("column_index") or 0):
        return ""
    return str(
        item.get("materialization_source_id") or item.get("parent_element_id") or ""
    ).strip()


def _parent_aliases(item: dict[str, Any]) -> set[str]:
    return {
        str(item.get(field) or "").strip()
        for field in (
            "evidence_id",
            "canonical_id",
            "element_id",
            "table_id",
            "table_instance_id",
        )
        if str(item.get(field) or "").strip()
    }


def materialize_financial_cell(item: dict[str, Any], cell: Any) -> dict[str, Any]:
    materialized = dict(item)
    materialized.pop("identity", None)
    materialized.pop("canonical_id", None)
    _drop_fields(materialized, _RUNTIME_IDENTITY_FIELDS)
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
            "source_id": cell.source_id,
            "file_id": cell.source_id or item.get("file_id") or "",
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
    if cell.column_header_path:
        metadata["column_header_path"] = list(cell.column_header_path)
    if cell.cell_id_aliases:
        metadata["cell_id_aliases"] = list(cell.cell_id_aliases)
    _drop_fields(metadata, _TRANSIENT_METADATA_FIELDS)
    materialized["metadata"] = metadata
    materialized["canonical_id"] = identity_of(materialized).key
    return materialized


def _drop_fields(payload: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        payload.pop(field, None)


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
    if identity_of(left).key == identity_of(right).key:
        return True
    if _explicit_parent_child_lineage(left, right):
        return True
    left_source = _source_id(left)
    right_source = _source_id(right)
    return bool(left_source and left_source == right_source)


def _explicit_parent_child_lineage(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    for child, parent in ((left, right), (right, left)):
        parent_id = str(child.get("materialization_source_id") or "").strip()
        parent_aliases = {
            str(parent.get(field) or "").strip()
            for field in ("evidence_id", "canonical_id", "element_id")
            if str(parent.get(field) or "").strip()
        }
        if parent_id and parent_id in parent_aliases:
            return True
    return False


def _source_id(item: dict[str, Any]) -> str:
    return source_identity(item)
