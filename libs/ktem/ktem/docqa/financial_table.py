from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .financial_statement_identity import financial_statement_identity

_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
_VALUE_RE = re.compile(
    r"(?:\$?\s*\([+-]?\d[\d,]*(?:\.\d+)?\)|" r"\(?[+-]?\$?\s*\d[\d,]*(?:\.\d+)?\)?)"
)


@dataclass(frozen=True, slots=True)
class FinancialTableCell:
    cell_id: str
    evidence_id: str
    canonical_id: str
    source_id: str
    page_label: str
    table_id: str
    row_index: int
    column_index: int
    row_label: str
    column_label: str
    period: str
    value: Decimal
    period_kind: str = ""
    unit: str = ""
    scale: str = ""
    currency: str = ""
    statement_kind: str = ""
    financial_scope: str = ""

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
    header_index, periods = _period_header(lines)
    if header_index is None or len(periods) < 2:
        return ()

    identity = _table_identity(item)
    statement_kind, financial_scope = financial_statement_identity(item)
    period_kind = _period_kind(item, text)
    scale = _dimension(item, "scale") or _scale(text)
    currency = _dimension(item, "currency") or _currency(text)
    unit = _dimension(item, "unit")
    cells: list[FinancialTableCell] = []
    row_index = 0
    for line in lines[header_index + 1 :]:
        if len(set(_YEAR_RE.findall(line))) >= 2:
            break
        parsed = _parse_row(line, periods)
        if parsed is None:
            continue
        row_label, values = parsed
        row_index += 1
        row_slug = _slug(row_label)
        for column_index, (period, value) in enumerate(
            zip(periods, values),
            start=1,
        ):
            cell_id = f"{identity['canonical_id']}#row:{row_slug}#column:{period}"
            cells.append(
                FinancialTableCell(
                    cell_id=cell_id,
                    evidence_id=identity["evidence_id"],
                    canonical_id=identity["canonical_id"],
                    source_id=identity["source_id"],
                    page_label=identity["page_label"],
                    table_id=identity["table_id"],
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
    headers = [
        index
        for index, line in enumerate(lines)
        if len(set(_YEAR_RE.findall(line))) >= 2
    ]
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
    return FinancialTableCell(
        cell_id=str(item.get("cell_id") or "").strip()
        or (
            f"{identity['canonical_id']}#row:{_slug(row_label)}"
            f"#column:{_slug(column_label)}"
        ),
        evidence_id=identity["evidence_id"],
        canonical_id=identity["canonical_id"],
        source_id=identity["source_id"],
        page_label=identity["page_label"],
        table_id=identity["table_id"],
        row_index=int(item.get("row_index") or 0),
        column_index=int(item.get("column_index") or 0),
        row_label=row_label,
        column_label=column_label,
        period=str(item.get("period") or column_label).strip(),
        value=value,
        period_kind=_period_kind(item, _item_text(item)),
        unit=_dimension(item, "unit"),
        scale=_dimension(item, "scale"),
        currency=_dimension(item, "currency"),
        statement_kind=statement_kind,
        financial_scope=financial_scope,
    )


def _period_header(lines: list[str]) -> tuple[int | None, tuple[str, ...]]:
    for index, line in enumerate(lines):
        periods = tuple(dict.fromkeys(_YEAR_RE.findall(line)))
        if len(periods) >= 2:
            return index, periods
    return None, ()


def _parse_row(
    line: str,
    periods: tuple[str, ...],
) -> tuple[str, tuple[Decimal, ...]] | None:
    matches = [
        match
        for match in _VALUE_RE.finditer(line)
        if not _bare_period_token(match.group(0), periods)
    ]
    if len(matches) < len(periods):
        return None
    row_label = line[: matches[0].start()].strip(" :.|-\t")
    if not row_label or _YEAR_RE.search(row_label):
        return None
    values = tuple(
        value
        for match in matches[-len(periods) :]
        if (value := _decimal(match.group(0))) is not None
    )
    if len(values) != len(periods):
        return None
    return row_label, values


def _bare_period_token(value: str, periods: tuple[str, ...]) -> bool:
    token = str(value or "").strip()
    return token in periods


def _table_identity(item: dict[str, Any]) -> dict[str, str]:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    evidence_id = _first(
        item.get("evidence_id"),
        item.get("element_id"),
        item.get("canonical_id"),
    )
    canonical_id = _first(item.get("canonical_id"), evidence_id, "financial-table")
    return {
        "evidence_id": evidence_id,
        "canonical_id": canonical_id,
        "source_id": _first(
            item.get("source_id"),
            item.get("document_id"),
            nested.get("source_id"),
        ),
        "page_label": _first(
            item.get("page_label"),
            item.get("page"),
            nested.get("page_label"),
        ),
        "table_id": _first(item.get("table_id"), item.get("element_id"), canonical_id),
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
        r")\s+(thousands?|millions?|billions?)\b",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).lower().rstrip("s") if match else ""


def _currency(text: str) -> str:
    lowered = text.lower()
    if "$" in text or "dollar" in lowered or "usd" in lowered:
        return "USD"
    if "eur" in lowered or "€" in text:
        return "EUR"
    if "gbp" in lowered or "£" in text:
        return "GBP"
    return ""


def _period_kind(item: dict[str, Any], text: str) -> str:
    explicit = _dimension(item, "period_kind")
    if explicit:
        return explicit
    lowered = str(text or "").lower()
    if "three months ended" in lowered or "quarter" in lowered:
        return "quarter"
    if any(
        phrase in lowered
        for phrase in ("twelve months ended", "fiscal year", "full year", "year ended")
    ):
        return "fiscal_year"
    return ""


def _decimal(value: Any) -> Decimal | None:
    text = str(value or "").replace("$", "").replace(",", "").replace(" ", "")
    negative = text.startswith("(") and text.endswith(")")
    try:
        parsed = Decimal(text.strip("()"))
    except InvalidOperation:
        return None
    return -parsed if negative else parsed


def _first(*values: Any) -> str:
    return next(
        (str(value).strip() for value in values if str(value or "").strip()),
        "",
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _normalized_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))
