from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from .financial_statement_identity import financial_statement_identity
from .financial_table_parser import decimal_value, section_rows


def parse_scoped_header_cells(
    item: dict[str, Any],
    text: str,
    lines: list[str],
) -> tuple[Any, ...]:
    reported_adjusted = _reported_adjusted_measure_cells(item, text, lines)
    if reported_adjusted:
        return reported_adjusted
    dual_period = _dual_period_measure_cells(item, text, lines)
    if dual_period:
        return dual_period
    quarterly = _quarterly_fiscal_table_cells(item, text, lines)
    return quarterly or _consolidating_table_cells(item, text, lines)


def _reported_adjusted_measure_cells(
    item: dict[str, Any],
    text: str,
    lines: list[str],
) -> tuple[Any, ...]:
    header = next(
        (line for line in lines if "adjusted non-gaap results" in line.lower()),
        "",
    )
    periods = tuple(re.findall(r"\b(?:19|20)\d{2}\b", header))
    if len(periods) < 2:
        return ()
    metric_patterns = (
        ("Adjusted EBITDA", re.compile(r"^EBITDA\b", re.IGNORECASE)),
        ("Adjusted EBIT", re.compile(r"^EBIT\b", re.IGNORECASE)),
        ("Adjusted Net Income", re.compile(r"^Net income\b", re.IGNORECASE)),
        ("Adjusted EPS", re.compile(r"^EPS\b", re.IGNORECASE)),
    )
    number_pattern = re.compile(r"(?<![A-Za-z0-9])\(?-?\d[\d,]*(?:\.\d+)?\)?")
    rows = []
    for metric, pattern in metric_patterns:
        line = next((value for value in lines if pattern.search(value.strip())), "")
        values = tuple(
            decimal_value(match.group(0)) for match in number_pattern.finditer(line)
        )
        if len(values) >= 2 and values[0] is not None and values[1] is not None:
            rows.append((metric, (values[0], values[1])))
    if not rows:
        return ()
    paired_columns = tuple(
        (period, period, "fiscal_year", "fiscal_year", "") for period in periods[:2]
    )
    return _scoped_cells(item, text, rows, paired_columns)


def _dual_period_measure_cells(
    item: dict[str, Any],
    text: str,
    lines: list[str],
) -> tuple[Any, ...]:
    header = re.search(
        r"Twelve Months Ended.*?\b((?:19|20)\d{2})\b.*?"
        r"Twelve Months Ended.*?\b((?:19|20)\d{2})\b",
        " ".join(lines),
        flags=re.IGNORECASE,
    )
    normalized = " ".join(re.findall(r"[a-z0-9]+", text.lower()))
    if header is None or not all(
        metric in normalized for metric in ("ebitda", "income", "eps")
    ):
        return ()
    rows = []
    number_pattern = re.compile(r"(?<![A-Za-z0-9])\(?-?\d[\d,]*(?:\.\d+)?\)?")
    for line in lines:
        matches = list(number_pattern.finditer(line))
        if len(matches) != 8:
            continue
        label = line[: matches[0].start()].strip(" ,:.-")
        values = tuple(decimal_value(match.group(0)) for match in matches)
        if label and all(value is not None for value in values):
            rows.append((label, values))
    if not rows:
        return ()
    periods = header.groups()
    metrics = ("EBITDA", "EBIT", "Net Income", "EPS")
    expanded_rows = []
    for label, values in rows:
        adjusted = label.lower().startswith("adjusted ")
        for metric_index, metric in enumerate(metrics):
            metric_label = f"Adjusted {metric}" if adjusted else metric
            expanded_rows.append(
                (
                    metric_label,
                    (values[metric_index], values[metric_index + len(metrics)]),
                )
            )
    paired_columns = (
        (periods[0], periods[0], "fiscal_year", "fiscal_year", ""),
        (periods[1], periods[1], "fiscal_year", "fiscal_year", ""),
    )
    return _scoped_cells(item, text, expanded_rows, paired_columns)


def table_dimensions(
    item: dict[str, Any],
    text: str,
) -> tuple[str, str, str, str, str]:
    from .financial_table import _currency, _dimension, _scale

    text_kind, text_scope = financial_statement_identity(text)
    explicit_kind, explicit_scope = financial_statement_identity(item)
    return (
        text_kind or explicit_kind,
        text_scope or explicit_scope,
        _dimension(item, "unit"),
        _dimension(item, "scale") or _scale(text),
        _dimension(item, "currency") or _currency(text),
    )


def _consolidating_table_cells(
    item: dict[str, Any],
    text: str,
    lines: list[str],
) -> tuple[Any, ...]:
    normalized = " ".join(re.findall(r"[a-z0-9]+", text.lower()))
    if "consolidating" not in normalized or "consolidated" not in normalized:
        return ()
    year_match = re.search(r"\b((?:19|20)\d{2})\b", text)
    if year_match is None:
        return ()
    period = year_match.group(1)
    headers = (
        ("Parent", "parent"),
        ("Guarantor Subsidiary Issuer", "guarantor_subsidiary_issuer"),
        ("Non-Guarantor Subsidiaries", "non_guarantor_subsidiaries"),
        ("Eliminations", "eliminations"),
        ("Consolidated", "consolidated"),
    )
    value_pattern = re.compile(
        r"(?<![A-Za-z0-9])(?:\(?-?\d[\d,]*(?:\.\d+)?\)?|[—–-])(?![A-Za-z0-9])"
    )
    rows = []
    for line in lines:
        matches = list(value_pattern.finditer(line))
        if len(matches) != len(headers):
            continue
        label = line[: matches[0].start()].strip(" :.|-\t")
        values = tuple(_consolidating_value(match.group(0)) for match in matches)
        if label and all(value is not None for value in values):
            rows.append((label, values))
    return _scoped_cells(
        item,
        text,
        rows,
        tuple((header, period, "fiscal_year", "", scope) for header, scope in headers),
    )


def _quarterly_fiscal_table_cells(
    item: dict[str, Any],
    text: str,
    lines: list[str],
) -> tuple[Any, ...]:
    metadata = dict(item.get("metadata") or {})
    source_name = next(
        (
            str(value).strip()
            for value in (
                item.get("source_name"),
                item.get("file_name"),
                metadata.get("source_name"),
            )
            if str(value or "").strip()
        ),
        "",
    )
    report_match = re.search(
        r"(?P<year>(?:19|20)\d{2})Q(?P<quarter>[1-4])",
        source_name,
        flags=re.IGNORECASE,
    )
    if report_match is None:
        return ()
    date_pattern = re.compile(
        r"\b(?:January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+\d{1,2},\s+(?:19|20)\d{2}\b",
        flags=re.IGNORECASE,
    )
    header = _date_header(lines, date_pattern)
    if header is None:
        return ()
    header_index, dates = header
    report_year = int(report_match.group("year"))
    parser_periods = (
        str(report_year),
        str(report_year - 1),
        f"{report_year - 1}-Q{report_match.group('quarter')}",
    )
    rows = section_rows(lines[header_index + 1 :], parser_periods)
    columns = (
        (dates[0], str(report_year), "quarter", "quarter", ""),
        (dates[1], str(report_year - 1), "fiscal_year", "fiscal_year", ""),
        (dates[2], str(report_year - 1), "quarter", "quarter", ""),
    )
    return _scoped_cells(item, text, rows, columns)


def _date_header(
    lines: list[str],
    pattern: re.Pattern[str],
) -> tuple[int, tuple[str, ...]] | None:
    for index, line in enumerate(lines):
        dates = tuple(match.group(0) for match in pattern.finditer(line))
        if len(dates) >= 3:
            return index, dates[:3]
    return None


def _scoped_cells(
    item: dict[str, Any],
    text: str,
    rows: Any,
    columns: tuple[tuple[str, str, str, str, str], ...],
) -> tuple[Any, ...]:
    from .financial_table import (
        FinancialTableCell,
        PhysicalCellIdentity,
        _currency,
        _dimension,
        _scale,
        _table_identity,
    )

    identity = _table_identity(item)
    statement_kind, table_scope = financial_statement_identity(text)
    scale = _dimension(item, "scale") or _scale(text)
    currency = _dimension(item, "currency") or _currency(text)
    unit = _dimension(item, "unit")
    cells = []
    for row_index, (row_label, values) in enumerate(rows, start=1):
        for column_index, (column, value) in enumerate(
            zip(columns, values),
            start=1,
        ):
            label, period, period_kind, path_kind, scope = column
            physical = PhysicalCellIdentity(
                source_id=identity["source_id"],
                page_label=identity["page_label"],
                table_instance_id=identity["table_instance_id"],
                block_id=identity["block_id"],
                row_index=row_index,
                column_index=column_index,
            )
            header_path = (label, period) if not path_kind else (label, f"FY{period}")
            cells.append(
                FinancialTableCell(
                    cell_id=physical.key,
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
                    column_label=(f"{label} | {period}" if scope else label),
                    column_header_path=header_path,
                    period=period,
                    value=value,
                    period_kind=period_kind,
                    unit=unit,
                    scale=scale,
                    currency=currency,
                    statement_kind=statement_kind,
                    financial_scope=scope or table_scope,
                )
            )
    return tuple(cells)


def _consolidating_value(value: str) -> Decimal | None:
    if str(value or "").strip() in {"—", "–", "-"}:
        return Decimal("0")
    return decimal_value(value)
