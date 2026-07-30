from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from .financial_statement_identity import financial_statement_identity
from .financial_table_parser import decimal_value as _decimal
from .financial_table_parser import period_header_records as _period_header_records
from .financial_table_parser import period_kind as _period_kind
from .financial_table_parser import period_sections as _period_sections
from .financial_table_parser import section_rows as _section_rows
from .financial_table_parser import (
    trailing_period_header_label as _trailing_period_header_label,
)


@dataclass(frozen=True, slots=True)
class PhysicalCellIdentity:
    source_id: str
    page_label: str
    table_instance_id: str
    block_id: str
    row_index: int
    column_index: int

    @property
    def key(self) -> str:
        return "#".join(
            (
                f"source:{_identity_component(self.source_id)}",
                f"page:{_identity_component(self.page_label)}",
                f"table-instance:{_identity_component(self.table_instance_id)}",
                f"block:{_identity_component(self.block_id)}",
                f"row:{self.row_index}",
                f"column:{self.column_index}",
            )
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SemanticCellKey:
    metric: str
    period: str
    statement_kind: str
    financial_scope: str
    unit: str
    scale: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FinancialTableCell:
    cell_id: str
    evidence_id: str
    canonical_id: str
    source_id: str
    page_label: str
    table_id: str
    table_instance_id: str
    table_group_id: str
    block_id: str
    row_index: int
    column_index: int
    row_label: str
    column_label: str
    period: str
    value: Decimal
    cell_role: str = "data"
    period_kind: str = ""
    unit: str = ""
    scale: str = ""
    currency: str = ""
    statement_kind: str = ""
    financial_scope: str = ""

    @property
    def physical_identity(self) -> PhysicalCellIdentity:
        return PhysicalCellIdentity(
            source_id=self.source_id,
            page_label=self.page_label,
            table_instance_id=self.table_instance_id,
            block_id=self.block_id,
            row_index=self.row_index,
            column_index=self.column_index,
        )

    @property
    def semantic_key(self) -> SemanticCellKey:
        return SemanticCellKey(
            metric=_slug(self.row_label).replace("-", "_"),
            period=self.period,
            statement_kind=self.statement_kind,
            financial_scope=self.financial_scope,
            unit=self.unit,
            scale=self.scale,
        )

    def verification_text(self) -> str:
        return " ".join(
            value
            for value in (
                self.row_label,
                self.column_label,
                self.period_kind,
                str(self.value),
                self.unit,
                self.scale,
                self.currency,
                self.statement_kind,
                self.financial_scope,
                self.cell_role,
            )
            if value
        )


def parse_financial_table_cells(
    item: dict[str, Any],
) -> tuple[FinancialTableCell, ...]:
    explicit = _explicit_cell(item)
    if explicit is not None:
        return (explicit,)
    text = _item_text(item)
    if not text:
        return ()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    sections = _period_sections(lines, item)
    if not sections:
        return ()

    identity = _table_identity(item)
    text_statement_kind, text_financial_scope = financial_statement_identity(text)
    explicit_statement_kind, explicit_financial_scope = financial_statement_identity(
        item
    )
    statement_kind = text_statement_kind or explicit_statement_kind
    financial_scope = text_financial_scope or explicit_financial_scope
    scale = _dimension(item, "scale") or _scale(text)
    currency = _dimension(item, "currency") or _currency(text)
    unit = _dimension(item, "unit")
    cells: list[FinancialTableCell] = []
    row_index = 0
    disambiguate_period_kind = len(sections) > 1
    for header_index, end_index, periods, period_kind in sections:
        rows = _rows_for_period_section(
            lines,
            header_index,
            end_index,
            periods,
        )
        for row_label, values in rows:
            row_index += 1
            for column_index, (period, value) in enumerate(
                zip(periods, values),
                start=1,
            ):
                physical_block_id = (
                    f"{identity['block_id']}:{period_kind or 'unspecified'}"
                    if disambiguate_period_kind
                    else identity["block_id"]
                )
                physical_identity = PhysicalCellIdentity(
                    source_id=identity["source_id"],
                    page_label=identity["page_label"],
                    table_instance_id=identity["table_instance_id"],
                    block_id=physical_block_id,
                    row_index=row_index,
                    column_index=column_index,
                )
                cells.append(
                    FinancialTableCell(
                        cell_id=physical_identity.key,
                        evidence_id=identity["evidence_id"],
                        canonical_id=identity["canonical_id"],
                        source_id=identity["source_id"],
                        page_label=identity["page_label"],
                        table_id=identity["table_id"],
                        table_instance_id=identity["table_instance_id"],
                        table_group_id=identity["table_group_id"],
                        block_id=physical_block_id,
                        row_index=row_index,
                        column_index=column_index,
                        row_label=row_label,
                        column_label=period,
                        period=period,
                        value=value,
                        period_kind=period_kind,
                        unit=unit,
                        scale=scale,
                        currency=currency,
                        statement_kind=statement_kind,
                        financial_scope=financial_scope,
                    )
                )
    return tuple(cells)


def _rows_for_period_section(
    lines: list[str],
    header_index: int,
    end_index: int,
    periods: tuple[str, ...],
) -> tuple[tuple[str, tuple[Decimal, ...]], ...]:
    initial_label = _trailing_period_header_label(lines[header_index], periods)
    return _section_rows(
        lines[header_index + 1 : end_index],
        periods,
        initial_label=initial_label,
    )


def find_financial_cell(
    evidence_items: list[dict[str, Any]],
    *,
    aliases: tuple[str, ...],
    period: str = "",
    expected_value: Decimal | None = None,
    period_kind: str = "",
    excluded_cell_ids: set[str] | None = None,
    statement_kind: str = "",
    financial_scope: str = "",
) -> FinancialTableCell | None:
    excluded = excluded_cell_ids or set()
    ranked: list[tuple[int, int, int, FinancialTableCell]] = []
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
            ranked.append((-value_match, -support, item_index, cell))
    if not ranked:
        return None
    if expected_value is not None and not any(row[0] == -1 for row in ranked):
        return None
    return min(ranked, key=lambda row: row[:3])[3]


def find_financial_cell_by_id(
    item: dict[str, Any],
    cell_id: str,
) -> FinancialTableCell | None:
    return next(
        (cell for cell in parse_financial_table_cells(item) if cell.cell_id == cell_id),
        None,
    )


def financial_table_yearly_amounts(
    text: str,
    aliases: tuple[str, ...],
) -> dict[str, float]:
    rows: dict[str, tuple[int, dict[str, float]]] = {}
    for block_index, block in enumerate(_table_blocks(text), start=1):
        cells = parse_financial_table_cells(
            {
                "evidence_id": f"combined-financial-table-{block_index}",
                "element_type": "table",
                "text": block,
            }
        )
        for cell in cells:
            support = _metric_support(cell.row_label, aliases)
            if support == 0:
                continue
            row = rows.setdefault(cell.row_label, (support, {}))
            row[1][cell.period] = float(cell.value)
    if not rows:
        return {}
    return max(rows.values(), key=lambda row: row[0])[1]


def _table_blocks(text: str) -> tuple[str, ...]:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    headers = [start for start, _end, _periods in _period_header_records(lines)]
    return tuple(
        "\n".join(lines[max(0, start - 1) : end])
        for start, end in zip(headers, [*headers[1:], len(lines)])
    )


def _explicit_cell(item: dict[str, Any]) -> FinancialTableCell | None:
    row_label = str(item.get("row_label") or "").strip()
    column_label = str(item.get("column_label") or item.get("period") or "").strip()
    raw_value = item.get("value")
    if not row_label or not column_label or raw_value in (None, ""):
        return None
    value = _decimal(raw_value)
    if value is None:
        return None
    identity = _table_identity(item)
    statement_kind, financial_scope = financial_statement_identity(item)
    row_index = int(item.get("row_index") or 0)
    column_index = int(item.get("column_index") or 0)
    physical_identity = PhysicalCellIdentity(
        source_id=identity["source_id"],
        page_label=identity["page_label"],
        table_instance_id=identity["table_instance_id"],
        block_id=identity["block_id"],
        row_index=row_index,
        column_index=column_index,
    )
    return FinancialTableCell(
        cell_id=str(item.get("cell_id") or "").strip() or physical_identity.key,
        evidence_id=identity["evidence_id"],
        canonical_id=identity["canonical_id"],
        source_id=identity["source_id"],
        page_label=identity["page_label"],
        table_id=identity["table_id"],
        table_instance_id=identity["table_instance_id"],
        table_group_id=identity["table_group_id"],
        block_id=identity["block_id"],
        row_index=row_index,
        column_index=column_index,
        row_label=row_label,
        column_label=column_label,
        period=str(item.get("period") or column_label).strip(),
        value=value,
        cell_role=str(item.get("cell_role") or "data").strip().lower(),
        period_kind=_period_kind(item, _item_text(item)),
        unit=_dimension(item, "unit"),
        scale=_dimension(item, "scale"),
        currency=_dimension(item, "currency"),
        statement_kind=statement_kind,
        financial_scope=financial_scope,
    )


def _table_identity(item: dict[str, Any]) -> dict[str, str]:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    evidence_id = _first(
        item.get("evidence_id"),
        item.get("element_id"),
        item.get("canonical_id"),
    )
    canonical_id = _first(item.get("canonical_id"), evidence_id, "financial-table")
    source_id = _first(
        item.get("source_id"),
        item.get("document_id"),
        nested.get("source_id"),
    )
    page_label = _first(
        item.get("page_label"),
        item.get("page"),
        nested.get("page_label"),
    )
    table_id = _first(item.get("table_id"), item.get("element_id"), canonical_id)
    table_instance_id = _first(
        item.get("table_instance_id"),
        nested.get("table_instance_id"),
        table_id,
    )
    table_group_id = _first(
        item.get("table_group_id"),
        nested.get("table_group_id"),
        item.get("continuation_id"),
        nested.get("continuation_id"),
        table_id,
    )
    block_id = _first(
        item.get("block_id"),
        nested.get("block_id"),
        nested.get("parser_source_doc_id"),
        table_instance_id,
    )
    return {
        "evidence_id": evidence_id,
        "canonical_id": canonical_id,
        "source_id": source_id,
        "page_label": page_label,
        "table_id": table_id,
        "table_instance_id": table_instance_id,
        "table_group_id": table_group_id,
        "block_id": block_id,
    }


def _metric_support(row_label: str, aliases: tuple[str, ...]) -> int:
    row = _normalized_text(row_label)
    row_tokens = set(row.split())
    best = 0
    for alias in aliases:
        normalized_alias = _normalized_text(alias)
        alias_tokens = set(normalized_alias.split())
        if not alias_tokens:
            continue
        if row == normalized_alias:
            best = max(best, 3)
        elif normalized_alias in row or row in normalized_alias:
            best = max(best, 2)
        elif len(alias_tokens & row_tokens) / len(alias_tokens) >= 0.75:
            best = max(best, 1)
    return best


def _item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if item.get(field)
    )


def _dimension(item: dict[str, Any], field: str) -> str:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    return str(item.get(field) or nested.get(field) or "").strip()


def _scale(text: str) -> str:
    match = re.search(
        r"(?:"
        r"\(?\s*in|"
        r"dollars?\s+(?:are\s+)?(?:presented\s+)?in|"
        r"tabular\s+dollars?\s+(?:are\s+)?(?:presented\s+)?in"
        r")\s+(thousands?|millions?|billions?)\b|"
        r"\(\s*(thousands?|millions?|billions?)\s*\)",
        text,
        flags=re.IGNORECASE,
    )
    return (
        next(value for value in match.groups() if value).lower().rstrip("s")
        if match
        else ""
    )


def _currency(text: str) -> str:
    lowered = text.lower()
    if "$" in text or "dollar" in lowered or "usd" in lowered:
        return "USD"
    if "eur" in lowered or "€" in text:
        return "EUR"
    if "gbp" in lowered or "£" in text:
        return "GBP"
    return ""


def _first(*values: Any) -> str:
    return next(
        (str(value).strip() for value in values if str(value or "").strip()),
        "",
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _identity_component(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._~-]+", "_", str(value or "").strip()) or "unknown"


def _normalized_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))
