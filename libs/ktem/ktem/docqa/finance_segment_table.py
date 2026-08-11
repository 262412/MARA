from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .evidence_identity import identity_of
from .finance_evidence_dimensions import evidence_scale

_SegmentValues = dict[str, dict[str, Decimal]]
_SegmentCellIds = dict[str, dict[str, str]]


def segment_title(value: str) -> str:
    return " ".join(
        token.upper() if token.lower() in {"amd", "gpu"} else token.capitalize()
        for token in str(value or "").strip().split()
    )


def vertical_segment_matrix(
    item: dict[str, Any],
    requested_periods: tuple[str, ...],
) -> tuple[_SegmentValues, _SegmentCellIds, str, str]:
    scale = evidence_scale(str(item.get("text") or ""), item)
    if not scale:
        return {}, {}, "", ""
    values, cell_ids = _vertical_segment_values(item, requested_periods)
    return values, cell_ids, _segment_unit(item), scale


def revenue_section_item(item: dict[str, Any]) -> dict[str, Any] | None:
    text = str(item.get("text") or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    heading_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.fullmatch(
                r"(?:net\s+)?(?:sales|revenue|revenues)\s*:?",
                line,
                flags=re.IGNORECASE,
            )
            or (
                re.search(
                    r"\b(?:net\s+)?(?:sales|revenue|revenues)\b",
                    line,
                    flags=re.IGNORECASE,
                )
                and "segment" in line.lower()
            )
        ),
        None,
    )
    if heading_index is None:
        return None
    end = next(
        (
            index
            for index in range(heading_index + 1, len(lines))
            if re.match(
                r"(?:total\s+(?:net\s+)?(?:sales|revenue)|operating\s+income)",
                lines[index],
                flags=re.IGNORECASE,
            )
        ),
        len(lines),
    )
    start = next(
        (
            index
            for index in range(heading_index - 1, max(-1, heading_index - 12), -1)
            if re.search(r"\byear\s+ended\b", lines[index], flags=re.IGNORECASE)
            or len(re.findall(r"\b(?:19|20)\d{2}\b", lines[index])) >= 2
        ),
        heading_index,
    )
    section = dict(item)
    section["text"] = "\n".join(lines[start:end])
    return section


def _vertical_segment_values(
    item: dict[str, Any],
    requested_periods: tuple[str, ...],
) -> tuple[dict[str, dict[str, Decimal]], dict[str, dict[str, str]]]:
    text = str(item.get("text") or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    periods = tuple(
        period
        for period in dict.fromkeys(re.findall(r"\b(?:19|20)\d{2}\b", text))
        if period in requested_periods
    )
    if len(periods) < 2:
        return {}, {}
    try:
        start = next(
            index + 1
            for index, line in enumerate(lines)
            if re.fullmatch(
                r"(?:net\s+)?(?:sales|revenue|revenues)\s*:?",
                line,
                flags=re.IGNORECASE,
            )
        )
    except StopIteration:
        return {}, {}
    end = next(
        (
            index
            for index in range(start, len(lines))
            if re.match(
                r"(?:total\s+(?:net\s+)?(?:sales|revenue)|operating\s+income)",
                lines[index],
                flags=re.IGNORECASE,
            )
        ),
        len(lines),
    )
    values: dict[str, dict[str, Decimal]] = {}
    cell_ids: dict[str, dict[str, str]] = {}
    index = start
    while index < end:
        label = lines[index]
        if not re.search(r"[A-Za-z]", label):
            index += 1
            continue
        numeric_values: list[Decimal] = []
        cursor = index + 1
        while cursor < end and not re.search(r"[A-Za-z]", lines[cursor]):
            value = _decimal_line(lines[cursor])
            if value is not None:
                numeric_values.append(value)
            cursor += 1
        if len(numeric_values) >= len(periods):
            entity = segment_title(label)
            values[entity] = dict(zip(periods, numeric_values[: len(periods)]))
            cell_ids[entity] = {
                period: f"{identity_of(item).key}:row:{index}:period:{period}"
                for period in periods
            }
        index = max(cursor, index + 1)
    return values, cell_ids


def _segment_unit(item: dict[str, Any]) -> str:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    explicit = str(
        item.get("unit")
        or item.get("currency")
        or nested.get("unit")
        or nested.get("currency")
        or ""
    ).strip()
    if explicit:
        return explicit
    return "USD" if "$" in str(item.get("text") or "") else ""


def _decimal_line(value: str) -> Decimal | None:
    text = str(value or "").strip().replace("$", "").replace(",", "")
    negative = text.startswith("(") and text.endswith(")")
    if not re.fullmatch(r"\(?[+-]?\d+(?:\.\d+)?\)?", text):
        return None
    try:
        parsed = Decimal(text.strip("()"))
    except InvalidOperation:
        return None
    return -parsed if negative else parsed
