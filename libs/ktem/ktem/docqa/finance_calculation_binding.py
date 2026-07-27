from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .query_evidence_constraints import atomic_evidence


def operand_period(name: str, question: str) -> str:
    years = re.findall(
        r"\b(?:fy\s*)?((?:19|20)\d{2})\b",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    name_period = re.search(r"(?:19|20)\d{2}", name)
    if name_period is not None:
        return name_period.group(0)
    if name == "prior" and years:
        return years[0]
    if name == "current" and len(years) >= 2:
        return years[1]
    if len(years) == 1:
        return years[0]
    return ""


def single_question_period(question: str) -> str:
    years = list(
        dict.fromkeys(
            re.findall(
                r"\b(?:fy\s*)?((?:19|20)\d{2})\b",
                str(question or ""),
                flags=re.IGNORECASE,
            )
        )
    )
    return years[0] if len(years) == 1 else ""


def shared_scale(operands: tuple[Any, ...]) -> str:
    values = {operand.scale for operand in operands if operand.scale}
    return values.pop() if len(values) == 1 else ""


def requested_scale(question: str) -> str:
    lowered = str(question or "").lower()
    for scale in ("billion", "million", "thousand"):
        if re.search(rf"\b{scale}s?\b", lowered):
            return scale
    return ""


def item_id(item: dict[str, Any] | None) -> str:
    if item is None:
        return ""
    return str(
        item.get("evidence_id")
        or item.get("element_id")
        or item.get("canonical_id")
        or ""
    ).strip()


def atomic_evidence_id(
    evidence_id: str,
    evidence_items: list[dict[str, Any]],
) -> bool:
    return any(
        item_id(item) == evidence_id and atomic_evidence(item)
        for item in evidence_items
    )


def atomic_item_value(item: dict[str, Any]) -> Decimal | None:
    if not atomic_evidence(item) or item.get("value") in (None, ""):
        return None
    try:
        return Decimal(str(item["value"]).replace(",", ""))
    except InvalidOperation:
        return None


def item_text(item: dict[str, Any] | None) -> str:
    if item is None:
        return ""
    return " ".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "vlm_text", "caption")
    )


def item_dimension(item: dict[str, Any] | None, field: str) -> str:
    if item is None:
        return ""
    metadata = dict(item.get("metadata") or {})
    return str(item.get(field) or metadata.get(field) or "").strip()


def decimal_values(text: str) -> list[Decimal]:
    values: list[Decimal] = []
    pattern = (
        r"(?:\$?\s*\([+-]?\d[\d,]*(?:\.\d+)?\)|" r"\(?[+-]?\$?\s*\d[\d,]*(?:\.\d+)?\)?)"
    )
    for raw in re.findall(pattern, text):
        normalized = raw.replace("$", "").replace(",", "").replace(" ", "")
        negative = "(" in normalized and normalized.endswith(")")
        try:
            parsed = Decimal(normalized.strip("()"))
        except InvalidOperation:
            continue
        values.append(-parsed if negative else parsed)
    return values
