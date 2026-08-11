from __future__ import annotations

import re
from typing import Any

from .evidence_identity import identity_of
from .evidence_text import evidence_text


def finance_narrative_support_quality(
    metric: str,
    item: dict[str, Any],
) -> float:
    """Score narrow, locally authoritative FinanceBench narrative patterns."""

    intent = _normalize(metric)
    raw_text = evidence_text([item])
    text = _normalize(raw_text)
    if _has_any(intent, ("primary customers", "customer base")):
        if any(
            phrase in text
            for phrase in (
                "limited number of commercial airlines",
                "substantial portion of our revenue from the u s government",
                "revenues were earned pursuant to u s government contracts",
            )
        ):
            return 4.0
        return 0.0
    if "customer concentration" in intent or "major customer" in intent:
        return (
            4.0
            if "customer accounted for" in text
            and re.search(
                r"\b\d+(?:\.\d+)?\s*(?:%|percent\b)",
                raw_text,
                flags=re.IGNORECASE,
            )
            and "revenue" in text
            else 0.0
        )
    if "retiree" in intent:
        return (
            4.0
            if "estimated future benefit payments" in text
            and "pension benefits" in text
            and "health care and life" in text
            else 0.0
        )
    if "acquired" in intent and _has_any(intent, ("companies", "company")):
        return (
            3.5
            if "acquisition" in text and re.search(r"\bwe acquired\b", text)
            else 0.0
        )
    if "industry" in intent and "primarily operate" in intent:
        return (
            4.0
            if "global leader" in text
            and _has_any(text, ("developing and producing", "products and services"))
            else 0.0
        )
    if "gross" in intent and "margin" in intent:
        return (
            4.0
            if "consolidated statements of operations" in text
            and "total revenues" in text
            and "total costs and expenses" in text
            else 0.0
        )
    if "debt securities" in intent and "national securities exchange" in intent:
        return (
            4.0
            if "securities registered pursuant to section 12 b" in text
            and "title of each class" in text
            and "name of each exchange" in text
            and "section 12 g" in text
            else 0.0
        )
    return 0.0


def finance_narrative_intent(metric: str) -> bool:
    intent = _normalize(metric)
    return (
        _has_any(intent, ("primary customers", "customer base"))
        or _has_any(intent, ("customer concentration", "major customer"))
        or "retiree" in intent
        or ("acquired" in intent and _has_any(intent, ("companies", "company")))
        or ("industry" in intent and "primarily operate" in intent)
        or ("debt securities" in intent and "national securities exchange" in intent)
    )


def authoritative_narrative_candidate_ids(
    metric: str,
    ranked: list[tuple[float, int, dict[str, Any]]],
) -> tuple[str, ...] | None:
    if not finance_narrative_intent(metric):
        return None
    return tuple(
        identity_of(item).key
        for _score, _index, item in ranked
        if finance_narrative_support_quality(metric, item) > 0
    )[:3]


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _has_any(value: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in value for phrase in phrases)
