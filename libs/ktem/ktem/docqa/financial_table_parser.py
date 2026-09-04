from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
_VALUE_RE = re.compile(
    r"(?:\$?\s*\([+-]?\d[\d,]*(?:\.\d+)?\)|" r"\(?[+-]?\$?\s*\d[\d,]*(?:\.\d+)?\)?)"
)


def period_sections(
    lines: list[str],
    item: dict[str, Any],
) -> tuple[tuple[int, int, tuple[str, ...], str], ...]:
    headers = period_header_records(lines)
    sections = []
    explicit_period_kind = _dimension(item, "period_kind")
    for header_position, (header_start, header_end, periods) in enumerate(headers):
        end_index = (
            headers[header_position + 1][0]
            if header_position + 1 < len(headers)
            else len(lines)
        )
        header_text = " ".join(lines[header_start : header_end + 1])
        section_heading = (
            header_text
            if period_kind({}, header_text)
            else " ".join(lines[max(0, header_start - 1) : header_end + 1])
        )
        section_kind = explicit_period_kind or period_kind({}, section_heading)
        sections.append((header_end, end_index, periods, section_kind))
    return tuple(sections)


def period_header_records(
    lines: list[str],
) -> list[tuple[int, int, tuple[str, ...]]]:
    headers: list[tuple[int, int, tuple[str, ...]]] = []
    occupied: set[int] = set()
    for index, line in enumerate(lines):
        periods = tuple(dict.fromkeys(_YEAR_RE.findall(line)))
        if len(periods) >= 2 and _table_like_period_header(line, periods):
            headers.append((index, index, periods))
            occupied.add(index)

    index = 0
    while index < len(lines):
        if index in occupied or _year_only(lines[index]) is None:
            index += 1
            continue
        start = index
        vertical_periods: list[str] = []
        while index < len(lines):
            period = _year_only(lines[index])
            if period is None:
                break
            vertical_periods.append(period)
            index += 1
        if len(set(vertical_periods)) >= 2:
            headers.append(
                (
                    start,
                    index - 1,
                    tuple(dict.fromkeys(vertical_periods)),
                )
            )
            occupied.update(range(start, index))
        elif index == start:
            index += 1
    headers.sort(key=lambda header: header[0])
    return headers


def section_rows(
    lines: list[str],
    periods: tuple[str, ...],
    *,
    initial_label: str = "",
) -> tuple[tuple[str, tuple[Decimal, ...]], ...]:
    rows: list[tuple[str, tuple[Decimal, ...]]] = []
    pending_label = str(initial_label or "").strip()
    index = 0
    while index < len(lines):
        line = lines[index]
        parsed = _parse_row(line, periods)
        if parsed is not None:
            rows.append(parsed)
            pending_label = ""
            index += 1
            continue

        matches = [
            match
            for match in _VALUE_RE.finditer(line)
            if not _bare_period_token(match.group(0), periods)
        ]
        if pending_label and len(matches) >= len(periods):
            selected = _row_value_matches(matches, len(periods))
            values = tuple(
                value
                for match in selected
                if (value := decimal_value(match.group(0))) is not None
            )
            if len(values) == len(periods):
                rows.append((pending_label, values))
                pending_label = _row_label_fragment(line[selected[-1].end() :])
                index += 1
                continue

        if pending_label:
            vertical_values = _vertical_row_values(
                lines,
                index,
                len(periods),
                periods,
            )
            if vertical_values is not None:
                values, consumed = vertical_values
                rows.append((pending_label, values))
                pending_label = ""
                index += consumed
                continue

        if not matches:
            fragment = _row_label_fragment(line)
            if fragment:
                pending_label = " ".join(
                    value for value in (pending_label, fragment) if value
                )
        else:
            pending_label = ""
        index += 1
    return tuple(rows)


def trailing_period_header_label(
    header_text: str,
    periods: tuple[str, ...],
) -> str:
    if not periods:
        return ""
    last_period_end = -1
    for match in _YEAR_RE.finditer(str(header_text or "")):
        if match.group(1) in periods:
            last_period_end = match.end()
    if last_period_end < 0:
        return ""
    trailing = str(header_text or "")[last_period_end:].strip(" :.|-\t")
    if not trailing or re.search(r"[%$0-9]", trailing):
        return ""
    if len(re.findall(r"[A-Za-z]+", trailing)) > 8:
        return ""
    return _row_label_fragment(trailing)


def period_kind(item: dict[str, Any], text: str) -> str:
    explicit = _dimension(item, "period_kind")
    if explicit:
        return explicit
    lowered = str(text or "").lower()
    if "three months ended" in lowered or "quarter" in lowered:
        return "quarter"
    if any(
        phrase in lowered
        for phrase in (
            "twelve months ended",
            "fiscal year",
            "full year",
            "year ended",
            "december 31",
        )
    ):
        return "fiscal_year"
    return ""


def decimal_value(value: Any) -> Decimal | None:
    text = str(value or "").replace("$", "").replace(",", "").replace(" ", "")
    negative = text.startswith("(") and text.endswith(")")
    try:
        parsed = Decimal(text.strip("()"))
    except InvalidOperation:
        return None
    return -parsed if negative else parsed


def cell_id_aliases(item: dict[str, Any]) -> tuple[str, ...]:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    raw = item.get("cell_id_aliases") or nested.get("cell_id_aliases") or ()
    if isinstance(raw, str):
        raw = (raw,)
    return tuple(str(value).strip() for value in raw if str(value).strip())


def _table_like_period_header(line: str, periods: tuple[str, ...]) -> bool:
    remainder = str(line)
    for period in periods:
        remainder = remainder.replace(period, " ")
    words = re.findall(r"[A-Za-z]+", remainder)
    return len(words) <= 8 and not re.search(r"[.!?]\s", remainder)


def _year_only(line: str) -> str | None:
    periods = tuple(dict.fromkeys(re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", line)))
    if len(periods) != 1 or len(line) > 32:
        return None
    remainder = line.replace(periods[0], " ")
    if re.search(r"\d{3,}", remainder):
        return None
    words = re.findall(r"[A-Za-z]+", remainder)
    months = {
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    }
    return periods[0] if {word.lower() for word in words} <= months else None


def _vertical_row_values(
    lines: list[str],
    start: int,
    count: int,
    periods: tuple[str, ...],
) -> tuple[tuple[Decimal, ...], int] | None:
    values: list[Decimal] = []
    index = start
    while index < len(lines) and len(values) < count:
        line = lines[index]
        if re.fullmatch(r"[$€£¥\s]+", line):
            index += 1
            continue
        matches = [
            match
            for match in _VALUE_RE.finditer(line)
            if not _bare_period_token(match.group(0), periods)
        ]
        remainder = _VALUE_RE.sub("", line).strip(" $€£¥|,:;()-")
        if len(matches) != 1 or remainder:
            return None
        value = decimal_value(matches[0].group(0))
        if value is None:
            return None
        values.append(value)
        index += 1
    if len(values) != count:
        return None
    return tuple(values), index - start


def _row_label_fragment(value: str) -> str:
    fragment = str(value or "").strip(" :.|-\t")
    if _normalized_text(fragment) in {
        "assets",
        "liabilities",
        "equity",
        "liabilities and equity",
    }:
        return ""
    return fragment if fragment and not _YEAR_RE.search(fragment) else ""


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
    selected = _row_value_matches(matches, len(periods))
    values = tuple(
        value
        for match in selected
        if (value := decimal_value(match.group(0))) is not None
    )
    if len(values) != len(periods):
        return None
    return row_label, values


def _row_value_matches(
    matches: list[re.Match[str]],
    period_count: int,
) -> list[re.Match[str]]:
    if period_count <= 0 or len(matches) <= period_count:
        return matches[:period_count]
    if len(matches) % period_count != 0:
        return matches[-period_count:]
    columns_per_period = len(matches) // period_count
    if columns_per_period == 2 and _amount_percentage_pairs(matches):
        return [matches[index] for index in range(0, len(matches), 2)]
    if columns_per_period > 1:
        return matches[-period_count:]
    return [
        matches[period_index * columns_per_period]
        for period_index in range(period_count)
    ]


def _amount_percentage_pairs(matches: list[re.Match[str]]) -> bool:
    values = [decimal_value(match.group(0)) for match in matches]
    if any(value is None for value in values):
        return False
    amounts = [value for value in values[::2] if value is not None]
    percentages = [value for value in values[1::2] if value is not None]
    return (
        bool(amounts)
        and len(amounts) == len(percentages)
        and all(abs(value) <= 100 for value in percentages)
        and any(abs(value) > 100 for value in amounts)
    )


def _bare_period_token(value: str, periods: tuple[str, ...]) -> bool:
    return str(value or "").strip() in periods


def _dimension(item: dict[str, Any], field: str) -> str:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    return str(item.get(field) or nested.get(field) or "").strip()


def _normalized_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))
