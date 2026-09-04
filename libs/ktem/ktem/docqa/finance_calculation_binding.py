from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .evidence_identity import identity_of
from .finance_scale import scale_from_text, source_scale_evidence
from .query_evidence_constraints import atomic_evidence

_SCALE_FACTORS = {
    "thousand": Decimal("1000"),
    "million": Decimal("1000000"),
    "billion": Decimal("1000000000"),
}
_CURRENCIES = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}


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


def item_for_id(
    evidence_id: str,
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not evidence_id:
        return None
    return next(
        (item for item in evidence_items if item_id(item) == evidence_id),
        None,
    )


def identity_for_raw_id(
    evidence_id: str,
    evidence_items: list[dict[str, Any]],
) -> str:
    item = item_for_id(evidence_id, evidence_items)
    if item is None:
        return ""
    payload = dict(item)
    payload.pop("identity", None)
    payload.pop("canonical_id", None)
    return identity_of(payload).key


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


def resolved_item_dimensions(
    name: str,
    item: dict[str, Any] | None,
    evidence_items: list[dict[str, Any]],
    *,
    aliases: tuple[str, ...],
) -> tuple[str, str, str, str]:
    text = item_text(item)
    explicit_currency = item_dimension(item, "currency")
    currency = explicit_currency or (
        "USD" if "$" in text or "usd" in text.lower() else ""
    )
    unit = item_dimension(item, "unit") or currency
    scale = item_dimension(item, "scale") or scale_from_text(text, aliases=aliases)
    scale_evidence_id = ""
    if scale:
        discovered_scale, discovered_id = source_scale_evidence(item, evidence_items)
        if discovered_scale == scale:
            scale_evidence_id = discovered_id
        elif (
            scale == "one"
            and item_dimension(item, "scale_provenance") == "local_currency_amount"
        ):
            scale_evidence_id = item_id(item)
    else:
        scale, scale_evidence_id = source_scale_evidence(item, evidence_items)
        locally_parsed_amount = bool(
            name.startswith("revolving_credit_capacity")
            and not item_dimension(item, "value")
            and "$" in text
        )
        if not scale and "$" in text and (explicit_currency or locally_parsed_amount):
            scale = "one"
            scale_evidence_id = item_id(item)
    return unit, scale, currency, scale_evidence_id


def named_currency_dimensions(text: str, value: Decimal) -> tuple[str, str]:
    matches: set[tuple[str, str]] = set()
    pattern = re.compile(
        r"(?P<currency>[$€£¥])\s*"
        r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*"
        r"(?P<scale>thousands?|millions?|billions?)\b",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(str(text or "")):
        scale = match.group("scale").lower().rstrip("s")
        parsed = Decimal(match.group("value").replace(",", ""))
        if parsed * _SCALE_FACTORS[scale] == abs(value):
            matches.add((scale, _CURRENCIES[match.group("currency")]))
    return next(iter(matches)) if len(matches) == 1 else ("", "")


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
