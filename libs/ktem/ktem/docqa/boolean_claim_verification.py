from __future__ import annotations

import re
from typing import Any

from .claim_support import meaningful_tokens
from .evidence_identity import identity_of
from .evidence_text import evidence_text, extract_final_answer_text


def boolean_evidence_assessment(
    prompt: str,
    answer: str,
    evidence_items: list[dict[str, Any]],
) -> tuple[str, str, tuple[str, ...], tuple[str, ...]] | None:
    answer_text = extract_final_answer_text(answer).strip().lower()
    match = re.match(r"^(yes|true|no|false)\b", answer_text)
    normalized = match.group(1) if match else ""
    aliases = {"yes": True, "true": True, "no": False, "false": False}
    if normalized not in aliases:
        return None
    proposition = str(prompt or "").strip()
    claim = f"{normalized}: {proposition}"
    proposition_tokens = meaningful_tokens(proposition)
    supporting: list[str] = []
    contradicting: list[str] = []
    for item in evidence_items:
        item_text = evidence_text([item])
        item_tokens = meaningful_tokens(item_text)
        overlap = proposition_tokens & item_tokens
        required = max(2, int(len(proposition_tokens) * 0.6))
        if len(overlap) < min(len(proposition_tokens), required):
            continue
        evidence_is_negative = _has_negation(item_text)
        expected_evidence_negation = _has_negation(proposition) ^ (
            not aliases[normalized]
        )
        target = (
            supporting
            if evidence_is_negative == expected_evidence_negation
            else contradicting
        )
        target.append(identity_of(item).key)
    status = (
        "conflicting"
        if supporting and contradicting
        else "supported"
        if supporting
        else "contradicted"
        if contradicting
        else "unknown"
    )
    return (
        claim,
        status,
        tuple(dict.fromkeys(supporting)),
        tuple(dict.fromkeys(contradicting)),
    )


def _has_negation(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:cannot|can't|didn't|doesn't|neither|never|no|not|without)\b",
            str(value or ""),
            flags=re.IGNORECASE,
        )
    )
