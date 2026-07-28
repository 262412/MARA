from __future__ import annotations

from typing import Any

from .evidence_identity import exact_evidence_aliases, identity_of
from .financial_table import parse_financial_table_cells


def calculation_evidence_lookup(
    items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in items:
        identifiers = [
            identity_of(item).key,
            item.get("cell_id"),
            item.get("evidence_id"),
            item.get("canonical_id"),
            item.get("element_id"),
            *(item.get("duplicate_evidence_ids") or []),
        ]
        for identifier in identifiers:
            value = str(identifier or "").strip()
            if value:
                output[value] = item
        for cell in parse_financial_table_cells(item):
            materialized = materialize_financial_cell(item, cell)
            for identifier in exact_evidence_aliases(materialized):
                output[identifier] = materialized
    return output


def materialize_financial_cell(item: dict[str, Any], cell: Any) -> dict[str, Any]:
    materialized = dict(item)
    materialized.pop("identity", None)
    materialized.pop("canonical_id", None)
    materialized.update(
        {
            "cell_id": cell.cell_id,
            "evidence_level": "cell",
            "table_id": cell.table_id,
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
        }
    )
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
