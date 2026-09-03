from __future__ import annotations

from decimal import Decimal
from typing import Any

from .financial_table import (
    FinancialTableCell,
    _metric_support,
    _statement_authority,
    parse_financial_table_cells,
)


def find_financial_cells(
    evidence_items: list[dict[str, Any]],
    *,
    aliases: tuple[str, ...],
    period: str = "",
    expected_value: Decimal | None = None,
    period_kind: str = "",
    excluded_cell_ids: set[str] | None = None,
    statement_kind: str = "",
    financial_scope: str = "",
) -> tuple[FinancialTableCell, ...]:
    """Return all ranked cells that satisfy the requested semantic filters."""

    excluded = excluded_cell_ids or set()
    ranked: list[tuple[int, int, int, int, FinancialTableCell]] = []
    for item_index, item in enumerate(evidence_items):
        for cell in parse_financial_table_cells(item):
            if cell.cell_id in excluded:
                continue
            if period and cell.period != period:
                continue
            if period_kind and cell.period_kind and cell.period_kind != period_kind:
                continue
            if (
                statement_kind
                and cell.statement_kind
                and cell.statement_kind != statement_kind
            ):
                continue
            if (
                financial_scope
                and cell.financial_scope
                and cell.financial_scope != financial_scope
            ):
                continue
            support = _metric_support(cell.row_label, aliases)
            if support == 0:
                continue
            value_match = int(
                expected_value is not None and cell.value == expected_value
            )
            ranked.append(
                (
                    -_statement_authority(cell),
                    -value_match,
                    -support,
                    item_index,
                    cell,
                )
            )
    if not ranked:
        return ()
    if expected_value is not None and not any(row[1] == -1 for row in ranked):
        return ()
    return tuple(row[4] for row in sorted(ranked, key=lambda row: row[:4]))


def unique_semantic_cell(
    candidates: tuple[FinancialTableCell, ...],
) -> FinancialTableCell | None:
    if not candidates:
        return None
    first_key = _semantic_cell_key(candidates[0])
    return (
        candidates[0]
        if all(_semantic_cell_key(cell) == first_key for cell in candidates)
        else None
    )


def _semantic_cell_key(cell: FinancialTableCell) -> tuple[Any, ...]:
    return (
        " ".join(cell.row_label.casefold().split()),
        cell.period,
        cell.period_kind,
        cell.value,
        cell.unit,
        cell.scale,
        cell.currency,
        cell.statement_kind,
        cell.financial_scope,
    )
