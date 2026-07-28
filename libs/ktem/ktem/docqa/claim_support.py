from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .domain_verifiers import domain_claim_supported
from .evidence_text import evidence_text


def claim_supported(
    claim: str,
    evidence_items: list[dict[str, Any]],
    *,
    prompt: str = "",
    domain: str = "",
) -> bool:
    domain_supported = domain_claim_supported(
        domain,
        claim,
        evidence_items,
        prompt=prompt,
    )
    if domain_supported is not None:
        return domain_supported
    if _direct_evidence_supports_claim(claim, evidence_items):
        return True
    if _claim_contradicts_evidence(claim, evidence_items):
        return False
    if _semantic_evidence_supports_claim(claim, evidence_items):
        return True
    claim_tokens = meaningful_tokens(claim)
    if not claim_tokens:
        return True
    evidence_tokens = meaningful_tokens(evidence_text(evidence_items))
    overlap = claim_tokens & evidence_tokens
    return _source_summary_supports_claim(prompt, overlap, evidence_tokens)


def item_supports_claim(
    claim: str,
    item: dict[str, Any],
    *,
    prompt: str,
) -> bool:
    item_text = evidence_text([item])
    if text_contradicts_claim(claim, item_text):
        return False
    claim_tokens = meaningful_tokens(claim)
    evidence_tokens = meaningful_tokens(item_text)
    if _short_evidence_supports_claim(evidence_tokens, claim_tokens):
        return True
    if _fact_coverage_supports_claim(evidence_tokens, claim_tokens):
        return True
    if _semantic_text_supports_claim(claim, item_text):
        return True
    return _source_summary_supports_claim(
        prompt,
        claim_tokens & evidence_tokens,
        evidence_tokens,
    )


def text_contradicts_claim(claim: str, evidence: str) -> bool:
    return (
        _year_conflict(claim, evidence)
        or _direction_conflict(claim, evidence)
        or _numeric_conflict(claim, evidence)
        or _negation_conflict(claim, evidence)
    )


def unsupported_threshold(*, mode: str, domain: str) -> float:
    if domain == "finance":
        return 0.9
    if mode == "strict":
        return 0.75
    return 0.85


def unsupported_confidence(
    claim: str,
    evidence_items: list[dict[str, Any]],
    *,
    prompt: str,
    domain: str,
    mode: str,
) -> float:
    domain_supported = domain_claim_supported(
        domain,
        claim,
        evidence_items,
        prompt=prompt,
    )
    if domain_supported is False:
        return 1.0
    if _claim_contradicts_evidence(claim, evidence_items):
        return 0.95
    claim_tokens = meaningful_tokens(claim)
    evidence_tokens = meaningful_tokens(evidence_text(evidence_items))
    if (
        _is_source_summary_prompt(prompt)
        and claim_tokens
        and not (claim_tokens & evidence_tokens)
    ):
        return 0.85
    if (
        mode == "strict"
        and domain != "finance"
        and _direction_markers(claim)
        and _direction_markers(evidence_text(evidence_items))
        and not (claim_tokens & evidence_tokens)
    ):
        return 0.78
    if not evidence_tokens and claim_tokens:
        return 0.8
    return 0.55


def meaningful_tokens(value: str) -> set[str]:
    stop_words = {
        "about",
        "after",
        "before",
        "does",
        "from",
        "have",
        "that",
        "this",
        "with",
    }
    return {
        normalized
        for token in re.findall(r"[a-zA-Z0-9]+", _token_text(value).lower())
        if (normalized := _normalize_token(token))
        and len(normalized) > 3
        and normalized not in stop_words
    }


def _direct_evidence_supports_claim(
    claim: str,
    evidence_items: list[dict[str, Any]],
) -> bool:
    claim_tokens = meaningful_tokens(claim)
    if not claim_tokens:
        return True
    for item in evidence_items:
        item_text = evidence_text([item])
        if text_contradicts_claim(claim, item_text):
            continue
        item_tokens = meaningful_tokens(item_text)
        if _short_evidence_supports_claim(item_tokens, claim_tokens):
            return True
        if _fact_coverage_supports_claim(item_tokens, claim_tokens):
            return True
    return False


def _fact_coverage_supports_claim(
    evidence_tokens: set[str],
    claim_tokens: set[str],
) -> bool:
    if not evidence_tokens or not claim_tokens:
        return False
    overlap = claim_tokens & evidence_tokens
    required = max(3, math.ceil(len(claim_tokens) * 0.75))
    return len(overlap) >= min(len(claim_tokens), required)


def _short_evidence_supports_claim(
    evidence_tokens: set[str],
    claim_tokens: set[str],
) -> bool:
    if not evidence_tokens or len(evidence_tokens) > 2:
        return False
    return evidence_tokens <= claim_tokens


def _claim_contradicts_evidence(
    claim: str,
    evidence_items: list[dict[str, Any]],
) -> bool:
    return any(
        text_contradicts_claim(claim, evidence_text([item])) for item in evidence_items
    )


def _numeric_conflict(claim: str, evidence: str) -> bool:
    claim_values = _fact_numbers(claim)
    evidence_values = _fact_numbers(evidence)
    return bool(
        claim_values
        and evidence_values
        and claim_values.isdisjoint(evidence_values)
        and _shared_claim_context(claim, evidence)
    )


def _fact_numbers(value: str) -> set[Decimal]:
    numbers: set[Decimal] = set()
    for match in re.finditer(r"(?<!\w)[+-]?\d[\d,]*(?:\.\d+)?%?", str(value or "")):
        raw = match.group(0).replace(",", "")
        if raw.endswith("%"):
            raw = raw[:-1]
        if re.fullmatch(r"(?:19|20)\d{2}", raw):
            continue
        try:
            numbers.add(Decimal(raw))
        except InvalidOperation:
            continue
    return numbers


def _semantic_evidence_supports_claim(
    claim: str,
    evidence_items: list[dict[str, Any]],
) -> bool:
    return any(
        _semantic_text_supports_claim(claim, evidence_text([item]))
        for item in evidence_items
    )


def _semantic_text_supports_claim(claim: str, evidence: str) -> bool:
    claim_concepts = _semantic_concepts(claim)
    evidence_concepts = _semantic_concepts(evidence)
    if not claim_concepts or claim_concepts.isdisjoint(evidence_concepts):
        return False
    claim_direction = _direction_markers(claim)
    evidence_direction = _direction_markers(evidence)
    return bool(claim_direction and claim_direction & evidence_direction)


def _semantic_concepts(value: str) -> set[str]:
    tokens = meaningful_tokens(value)
    return {
        concept
        for concept, concept_tokens in _SEMANTIC_CONCEPT_TOKENS.items()
        if tokens & concept_tokens
    }


def _year_conflict(claim: str, evidence: str) -> bool:
    claim_years = _years(claim)
    evidence_years = _years(evidence)
    return bool(
        claim_years
        and evidence_years
        and not claim_years.issubset(evidence_years)
        and _shared_claim_context(claim, evidence)
    )


def _direction_conflict(claim: str, evidence: str) -> bool:
    claim_direction = _direction_markers(claim)
    evidence_direction = _direction_markers(evidence)
    return bool(
        claim_direction
        and evidence_direction
        and claim_direction.isdisjoint(evidence_direction)
        and _shared_claim_context(claim, evidence)
    )


def _shared_claim_context(claim: str, evidence: str) -> bool:
    claim_tokens = meaningful_tokens(claim) - _DIRECTION_CONTEXT_TOKENS
    evidence_tokens = meaningful_tokens(evidence) - _DIRECTION_CONTEXT_TOKENS
    return bool(claim_tokens & evidence_tokens)


def _negation_conflict(claim: str, evidence: str) -> bool:
    return _has_negation(claim) != _has_negation(evidence) and _shared_claim_context(
        claim, evidence
    )


def _has_negation(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:cannot|can't|didn't|doesn't|neither|never|not|without)\b",
            str(value or ""),
            flags=re.IGNORECASE,
        )
    )


def _source_summary_supports_claim(
    prompt: str,
    overlap: set[str],
    evidence_tokens: set[str],
) -> bool:
    if not _is_source_summary_prompt(prompt):
        return False
    minimum_evidence_tokens = (
        8 if "structured data" in str(prompt or "").lower() else 20
    )
    if len(evidence_tokens) < minimum_evidence_tokens:
        return False
    return bool(overlap - _SUMMARY_GENERIC_TOKENS)


def _is_source_summary_prompt(prompt: str) -> bool:
    lowered = str(prompt or "").lower()
    return any(
        marker in lowered
        for marker in (
            "summarize",
            "summarise",
            "summary",
            "overview",
            "based only on the provided",
            "based only on the structured data",
        )
    )


def _years(value: str) -> set[str]:
    return set(re.findall(r"\b(?:19|20)\d{2}\b", str(value or "")))


def _direction_markers(value: str) -> set[str]:
    tokens = {
        _normalize_token(token)
        for token in re.findall(r"[a-zA-Z0-9]+", _token_text(value).lower())
    }
    markers: set[str] = set()
    if tokens & _POSITIVE_DIRECTION_TOKENS:
        markers.add("positive")
    if tokens & _NEGATIVE_DIRECTION_TOKENS:
        markers.add("negative")
    return markers


def _token_text(value: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value or ""))
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    return text.replace("_", " ").replace("-", " ")


def _normalize_token(token: str) -> str:
    value = str(token or "").lower()
    if len(value) > 4 and value.endswith("ies"):
        return f"{value[:-3]}y"
    if len(value) > 4 and value.endswith("s") and not value.endswith("ss"):
        return value[:-1]
    return value


_SUMMARY_GENERIC_TOKENS = {
    "article",
    "business",
    "customer",
    "experience",
    "include",
    "including",
    "overview",
    "overall",
    "provide",
    "review",
    "source",
    "summary",
}

_POSITIVE_DIRECTION_TOKENS = {
    "gain",
    "gained",
    "grow",
    "grew",
    "growth",
    "higher",
    "improve",
    "improved",
    "improves",
    "increase",
    "increased",
    "increases",
    "rise",
    "rises",
    "rising",
    "rose",
    "up",
}

_NEGATIVE_DIRECTION_TOKENS = {
    "decline",
    "declined",
    "declines",
    "decrease",
    "decreased",
    "decreases",
    "drop",
    "dropped",
    "drops",
    "fall",
    "falls",
    "fell",
    "lower",
    "loss",
    "lost",
    "reduce",
    "reduced",
    "reduces",
    "worse",
}

_DIRECTION_CONTEXT_TOKENS = _POSITIVE_DIRECTION_TOKENS | _NEGATIVE_DIRECTION_TOKENS

_SEMANTIC_CONCEPT_TOKENS = {
    "profitability": {
        "earning",
        "income",
        "margin",
        "profit",
        "profitability",
    },
}
