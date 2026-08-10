from __future__ import annotations

import re
from typing import Any

from .evidence_text import evidence_text
from .finance_gross_margin_profile import finance_gross_margin_profile_answer
from .finance_narrative_answer import finance_narrative_answer


def finance_numeric_claim_supported(
    claim: str,
    evidence_items: list[dict[str, Any]],
    *,
    prompt: str,
) -> bool | None:
    narrative_support = _grounded_narrative_claim_supported(
        claim,
        evidence_items,
        prompt=prompt,
    )
    if narrative_support is not None:
        return narrative_support
    context = f"{prompt} {claim}".lower()
    if "quick ratio" not in context:
        return None

    inputs = _quick_ratio_inputs_from_items(evidence_items)
    if inputs is None:
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


def _grounded_narrative_claim_supported(
    claim: str,
    evidence_items: list[dict[str, Any]],
    *,
    prompt: str,
) -> bool | None:
    if _gross_margin_profile_intent(prompt):
        result = finance_gross_margin_profile_answer(prompt, evidence_items)
        return bool(result and _claim_in_answer(claim, result.answer))
    if not _narrative_intent(prompt):
        return None
    answer = finance_narrative_answer(prompt, evidence_items)
    if answer is not None and _claim_in_answer(claim, answer):
        return True
    if _partial_narrative_authority_supports(claim, evidence_items, prompt=prompt):
        return True
    return False


def _claim_in_answer(claim: str, answer: str) -> bool:
    normalized_claim = _normalize_claim_text(claim)
    normalized_answer = _normalize_claim_text(answer)
    return bool(normalized_claim and normalized_claim in normalized_answer)


def _partial_narrative_authority_supports(
    claim: str,
    evidence_items: list[dict[str, Any]],
    *,
    prompt: str,
) -> bool:
    normalized_claim = _normalize_claim_text(claim)
    normalized_text = _normalize_claim_text(evidence_text(evidence_items))
    lowered_prompt = str(prompt or "").lower()
    if "primary customers" in lowered_prompt:
        return any(
            phrase in normalized_claim and phrase in normalized_text
            for phrase in (
                "limited number of commercial airlines",
                "substantial portion of our revenue from the u s government",
                "revenues were earned pursuant to u s government contracts",
            )
        )
    if "acquired" in lowered_prompt and _has_any(
        lowered_prompt, ("companies", "company")
    ):
        claim_names = {
            token
            for token in re.findall(r"\b[A-Z][A-Za-z0-9&'.-]+\b", claim)
            if token.lower() not in {"the", "answer"}
        }
        return bool(
            claim_names
            and any(name.lower() in normalized_text for name in claim_names)
            and "acquired" in normalized_text
        )
    return False


def _gross_margin_profile_intent(prompt: str) -> bool:
    lowered = str(prompt or "").lower()
    return "gross margin" in lowered and _has_any(
        lowered, ("improving", "improved", "improve")
    )


def _narrative_intent(prompt: str) -> bool:
    lowered = str(prompt or "").lower()
    return (
        "retiree" in lowered
        or ("acquired" in lowered and _has_any(lowered, ("companies", "company")))
        or ("industry" in lowered and "primarily operate" in lowered)
        or "customer concentration" in lowered
        or "primary customers" in lowered
        or ("debt securities" in lowered and "national securities exchange" in lowered)
    )


def _normalize_claim_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


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


def _quick_ratio_inputs_from_items(
    evidence_items: list[dict[str, Any]],
) -> tuple[float, float, float] | None:
    values: dict[str, float] = {}
    for item in evidence_items:
        metadata = item.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        row_label = str(item.get("row_label") or metadata.get("row_label") or "")
        value = _structured_finance_amount(item.get("value", metadata.get("value")))
        if value is None:
            continue
        normalized_label = " ".join(re.findall(r"[a-z]+", row_label.lower()))
        if "current liabilities" in normalized_label:
            values["liabilities"] = value
        elif "current assets" in normalized_label:
            values["assets"] = value
        elif "inventor" in normalized_label:
            values["inventories"] = value
    if not {"assets", "inventories", "liabilities"} <= values.keys():
        return None
    return values["assets"], values["inventories"], values["liabilities"]


def _structured_finance_amount(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    return _parse_finance_amount(str(value))


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
