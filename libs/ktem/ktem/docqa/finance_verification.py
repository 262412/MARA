from __future__ import annotations

import re
from typing import Any

from .evidence_text import evidence_text


def finance_numeric_claim_supported(
    claim: str,
    evidence_items: list[dict[str, Any]],
    *,
    prompt: str,
) -> bool | None:
    context = f"{prompt} {claim}".lower()
    if "quick ratio" not in context:
        return None

    inputs = _quick_ratio_inputs(evidence_text(evidence_items))
    if inputs is None:
        return None
    ratios = _decimal_numbers(claim)

    assets, inventories, liabilities = inputs
    if liabilities == 0:
        return None
    expected = (assets - inventories) / liabilities
    if ratios:
        return any(abs(value - expected) <= 0.03 for value in ratios)
    return _quick_ratio_direction_supported(claim, expected)


def finance_verification_claims(claims: list[str], *, prompt: str) -> list[str]:
    if "quick ratio" not in str(prompt or "").lower():
        return claims
    focused = [claim for claim in claims if _is_quick_ratio_conclusion_claim(claim)]
    return focused or claims


def _is_quick_ratio_conclusion_claim(claim: str) -> bool:
    lowered = str(claim or "").lower()
    if "quick ratio" not in lowered:
        return False
    if re.search(r"\b\d+(?:\.\d+)?\b", lowered):
        return True
    conclusion_terms = (
        "below 1",
        "below the 1x",
        "less than 1",
        "under 1",
        "above 1",
        "greater than 1",
        "healthy liquidity",
        "liquidity profile",
    )
    return any(term in lowered for term in conclusion_terms)


def _quick_ratio_direction_supported(claim: str, expected: float) -> bool | None:
    lowered = str(claim or "").lower()
    if _has_any(lowered, ("below 1", "below the 1x", "less than 1", "under 1")):
        return expected < 1.0
    if _has_any(lowered, ("above 1", "greater than 1", "over 1")):
        return expected > 1.0
    if "liquidity" not in lowered or "healthy" not in lowered:
        return None
    negative = _has_any(
        lowered,
        ("not healthy", "not show", "does not show", "doesn't show", "no "),
    )
    return expected < 1.0 if negative else expected >= 1.0


def _has_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)


def _quick_ratio_inputs(text: str) -> tuple[float, float, float] | None:
    assets = _finance_amount_after(text, ["total current assets", "current assets"])
    inventories = _finance_amount_after(text, ["total inventories", "inventories"])
    liabilities = _finance_amount_after(
        text,
        ["total current liabilities", "current liabilities"],
    )
    if assets is None or inventories is None or liabilities is None:
        return None
    return assets, inventories, liabilities


def _finance_amount_after(text: str, labels: list[str]) -> float | None:
    for label in labels:
        pattern = rf"{re.escape(label)}[^\d(+-]*([(+\-]?\$?\s*[\d,]+(?:\.\d+)?)"
        match = re.search(pattern, str(text or ""), flags=re.IGNORECASE)
        if match:
            return _parse_finance_amount(match.group(1))
    return None


def _parse_finance_amount(value: str) -> float | None:
    text = str(value or "").replace("$", "").replace(",", "").strip()
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("() ")
    try:
        amount = float(text)
    except ValueError:
        return None
    return -amount if negative else amount


def _decimal_numbers(value: str) -> list[float]:
    numbers: list[float] = []
    for item in re.findall(r"\b\d+\.\d+\b", str(value or "")):
        try:
            numbers.append(float(item))
        except ValueError:
            continue
    return numbers
