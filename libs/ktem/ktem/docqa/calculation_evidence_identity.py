from __future__ import annotations

from typing import Any

from .evidence_identity import identity_of
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
            output[cell_identity(item, cell.cell_id)] = item
    return output


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
