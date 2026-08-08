from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ktem.docqa.boolean_evidence_scope import (
    _has_closed_quantifier,
    validate_boolean_scope,
)
from ktem.docqa.boolean_proposition_evidence import (
    boolean_proposition_binding_trace,
    classify_boolean_evidence_candidates,
)

from .qasper_boolean import (
    current_experiment_relation_polarity,
    quality_control_relation_polarity,
)
from .qasper_boolean_scope import evidence_item_text
from .qasper_quote_binding import (
    _bind_authoritative_quote,
    _BoundQuote,
    bind_evidence_ref_to_quote,
    evidence_ref_for_quote,
)

__all__ = [
    "AuthoritativeQuoteSupport",
    "authoritative_quote_binding_trace",
    "bind_evidence_ref_to_quote",
    "evidence_ref_for_quote",
    "parse_boolean_verdict",
    "quality_control_quote_for_verdict",
    "resolve_authoritative_quote_support",
    "resolve_verified_quote_support",
]


@dataclass(frozen=True)
class AuthoritativeQuoteSupport:
    evidence_id: str
    evidence_ref: str
    span_id: str
    quote: str
    claim_key: tuple[str, ...]
    polarity: str
    binding_status: str


def parse_boolean_verdict(answer: str) -> tuple[str, str, str]:
    try:
        payload = json.loads(str(answer or ""))
    except json.JSONDecodeError:
        return "", "", ""
    if not isinstance(payload, dict):
        return "", "", ""
    value = str(payload.get("verdict") or "")
    evidence_ref = str(payload.get("evidence_ref") or "").strip()
    quote = str(payload.get("evidence_quote") or "").strip()
    allowed = {
        "yes_complete",
        "no_complete",
        "yes_partial",
        "no_partial",
        "yes",
        "no",
        "insufficient_evidence",
    }
    if value not in allowed:
        return "", "", ""
    if value == "insufficient_evidence":
        return value, "", ""
    return value, evidence_ref, quote


def quality_control_quote_for_verdict(
    verdict: str,
    question: str,
    evidence_items: list[dict[str, Any]],
    *,
    fallback: str,
) -> str:
    if verdict not in {
        "no_complete",
        "yes_partial",
        "no_partial",
        "insufficient_evidence",
    }:
        return fallback
    matches: dict[str, str] = {}
    for item in evidence_items:
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", evidence_item_text(item)):
            quote = sentence.strip()
            if quality_control_relation_polarity(question, quote):
                matches[" ".join(quote.lower().split())] = quote
    if len(matches) != 1:
        return fallback
    return next(iter(matches.values()))


def resolve_verified_quote_support(
    question: str,
    evidence_ref: str,
    quote: str,
    verdict: str,
    reason: str,
    quote_supports_relation: bool,
    evidence_items: list[dict[str, Any]] | None,
    *,
    alias_mapping: str = "",
) -> tuple[str, bool, str, AuthoritativeQuoteSupport | None]:
    support = None
    if verdict in {"yes", "no"} and reason in {
        "grounded_complete_proposition",
        "grounded_complete_relation",
    }:
        if not _other_than_quote_supports_polarity(question, quote, verdict):
            return (
                "insufficient_evidence",
                False,
                "other_than_alternative_unproven",
                None,
            )
        bound, binding_status = _bind_authoritative_quote(
            evidence_ref,
            quote,
            evidence_items,
            alias_mapping=alias_mapping,
        )
        if bound is None:
            return "insufficient_evidence", False, binding_status, None
        support = _authoritative_support_from_bound(
            question,
            verdict,
            quote,
            bound,
        )
        if support is None:
            return (
                "insufficient_evidence",
                False,
                "polarity_authority_unproven",
                None,
            )
    return verdict, quote_supports_relation, reason, support


def authoritative_quote_binding_trace(
    question: str,
    selected_answer: str,
    evidence_items: list[dict[str, Any]],
    support: AuthoritativeQuoteSupport | None,
) -> dict[str, Any]:
    trace = boolean_proposition_binding_trace(
        question,
        selected_answer,
        evidence_items,
    )
    if support is None or selected_answer != support.polarity:
        return trace
    trace.update(
        {
            "authoritative_quote_evidence_id": support.evidence_id,
            "authoritative_claim_key": list(support.claim_key),
            "evidence_ref": support.evidence_ref,
            "authoritative_quote_span_id": support.span_id,
            "bound_support_evidence_ids": [support.evidence_id],
            "final_support_evidence_ids": [support.evidence_id],
            "binding_status": "verified_support",
            "evidence_ref_binding_status": support.binding_status,
            "evidence_ref_rebound": str(
                support.binding_status == "evidence_ref_rebound"
            ).lower(),
        }
    )
    return trace


def resolve_authoritative_quote_support(
    question: str,
    quote: str,
    polarity: str,
    evidence_items: list[dict[str, Any]] | None,
    *,
    evidence_ref: str = "",
    alias_mapping: str = "",
) -> AuthoritativeQuoteSupport | None:
    bound, _status = _bind_authoritative_quote(
        evidence_ref,
        quote,
        evidence_items,
        alias_mapping=alias_mapping,
    )
    if bound is None:
        return None
    return _authoritative_support_from_bound(question, polarity, quote, bound)


def _authoritative_support_from_bound(
    question: str,
    polarity: str,
    quote: str,
    bound: _BoundQuote,
) -> AuthoritativeQuoteSupport | None:
    item = bound.item
    quote_item = {
        **item,
        "text": evidence_item_text(item)[bound.span.item_start : bound.span.item_end],
        "ocr_text": "",
        "vlm_text": "",
        "caption": "",
    }
    quality_control_polarity = quality_control_relation_polarity(question, quote)
    claim_key: tuple[str, ...]
    if quality_control_polarity == polarity:
        claim_key = ("current_paper", "quality_control", "constructed_datasets")
    else:
        assessments = classify_boolean_evidence_candidates(
            question, polarity, quote_item
        )
        if not assessments:
            return None
        eligible = [
            assessment
            for assessment in assessments
            if _polarity_authority_is_proven(
                question,
                quote,
                polarity,
                assessment,
            )
        ]
        if not eligible:
            return None
        assessment = max(eligible, key=_assessment_score)
        claim_key = assessment.proposition.claim_key
    return AuthoritativeQuoteSupport(
        evidence_id=bound.evidence_id,
        evidence_ref=bound.evidence_ref,
        span_id=bound.span.identity,
        quote=evidence_item_text(bound.item)[
            bound.span.item_start : bound.span.item_end
        ],
        claim_key=claim_key,
        polarity=polarity,
        binding_status=bound.binding_status,
    )


def _assessment_score(value: Any) -> tuple[float, float]:
    return (
        value.relation_score * value.object_score,
        value.object_score,
    )


def _polarity_authority_is_proven(
    question: str,
    quote: str,
    polarity: str,
    assessment: Any,
) -> bool:
    if _has_closed_quantifier(question):
        quantified_scope = validate_boolean_scope(
            question,
            quote,
            polarity,
            evidence_items=[assessment.item],
        )
        if not quantified_scope.scope_valid:
            return False
    if (
        assessment.classification == "supports"
        and assessment.proposition.polarity == polarity
    ):
        return True
    if not (assessment.actor_score > 0 and assessment.scope_score > 0):
        return False
    if _explicit_semantic_polarity(question, quote) == polarity:
        return True
    if assessment.relation_score <= 0:
        return False
    if _other_than_exclusion(question):
        return _other_than_quote_supports_polarity(question, quote, polarity)
    if _effective_dependency_polarity(question, quote) == polarity:
        return True
    return _third_party_comparison_polarity(question, quote) == polarity


def _explicit_semantic_polarity(question: str, quote: str) -> str:
    for resolver in (
        _requirement_polarity,
        _qualitative_risk_polarity,
        _double_annotation_polarity,
        current_experiment_relation_polarity,
    ):
        polarity = resolver(question, quote)
        if polarity:
            return polarity
    return ""


def _requirement_polarity(question: str, quote: str) -> str:
    if not re.search(
        r"\b(?:require|required|requires|necessary|must)\b",
        str(question or ""),
        flags=re.IGNORECASE,
    ):
        return ""
    lowered = str(quote or "").lower()
    if re.search(
        r"\b(?:without|unnecessary|not required|does not require|"
        r"do not require|requires? no|optional|drop-in)\b",
        lowered,
    ):
        return "no"
    if re.search(r"\b(?:require|required|requires|necessary|must)\b", lowered):
        return "yes"
    return ""


def _qualitative_risk_polarity(question: str, quote: str) -> str:
    if not re.search(
        r"\b(?:downside|disadvantage|drawback|risk|harm|limitation)\b",
        str(question or ""),
        flags=re.IGNORECASE,
    ):
        return ""
    return (
        "yes"
        if re.search(
            r"\b(?:not a silver bullet|remove useful|risk|harm|degrad|"
            r"worse|limitation|drawback|disadvantage)\w*\b",
            str(quote or ""),
            flags=re.IGNORECASE,
        )
        else ""
    )


def _double_annotation_polarity(question: str, quote: str) -> str:
    if not re.search(
        r"\b(?:double|twice|two)\s+annotat\w*\b|\bannotat\w*\s+(?:twice|double)\b",
        str(question or ""),
        flags=re.IGNORECASE,
    ):
        return ""
    return (
        "yes"
        if re.search(
            r"\b(?:two|2)\s+annotators?\b|\bannotat\w*\s+(?:twice|independently by two)\b",
            str(quote or ""),
            flags=re.IGNORECASE,
        )
        else ""
    )


def _effective_dependency_polarity(question: str, quote: str) -> str:
    match = re.search(
        r"\b(?:is|are|was|were)\s+(.+?)\s+"
        r"(?:effective|beneficial|helpful|useful)\b",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    if match is None:
        return ""
    subject = " ".join(re.findall(r"[a-z0-9]+", match.group(1).lower()))
    normalized_quote = " ".join(re.findall(r"[a-z0-9]+", str(quote).lower()))
    if not subject or subject not in normalized_quote:
        return ""
    dependency = re.search(
        r"\b(?:cannot|can\s+not|can't|unable\s+to|fails?\s+to)\b"
        r"[^.!?]{0,100}\bwithout\b",
        str(quote or ""),
        flags=re.IGNORECASE,
    )
    return "yes" if dependency else ""


def _third_party_comparison_polarity(question: str, quote: str) -> str:
    comparison = re.search(
        r"\b(?:does|do|did)\s+(.+?)\s+outperform\s+(.+?)(?:\?|$)",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    if comparison is None:
        return ""
    subject = " ".join(comparison.group(1).lower().split())
    baseline = " ".join(comparison.group(2).lower().split())
    for match in re.finditer(
        r"\b([A-Z][A-Za-z0-9._-]*)\s+(?:consistently\s+)?"
        r"outperform(?:s|ed)?\s+([^.!?]+)",
        str(quote or ""),
    ):
        winner = match.group(1).lower()
        compared = match.group(2).lower()
        if winner != subject and subject in compared and baseline in compared:
            return "no"
    return ""


def _other_than_quote_supports_polarity(
    question: str,
    quote: str,
    polarity: str,
) -> bool:
    excluded = _other_than_exclusion(question)
    if not excluded:
        return True
    if polarity == "no":
        return _other_than_exclusivity_is_explicit(quote, excluded)
    if polarity != "yes":
        return False
    return _other_than_alternative_is_explicit(quote, excluded)


def _other_than_exclusion(question: str) -> str:
    match = re.search(
        r"\bother\s+than\s+([^,;?.]+)",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    if match is None:
        return ""
    return " ".join(match.group(1).strip().lower().split())


def _other_than_exclusivity_is_explicit(quote: str, excluded: str) -> bool:
    excluded_pattern = r"\s+".join(re.escape(part) for part in excluded.split() if part)
    if not excluded_pattern:
        return False
    patterns = (
        rf"\b(?:only|solely|exclusively)\b[^.!?]{{0,80}}\b{excluded_pattern}\b",
        rf"\b{excluded_pattern}\b[^.!?]{{0,40}}\b(?:only|solely|exclusively)\b",
        r"\bno\s+other\b",
        rf"\b(?:none|nothing)\b[^.!?]{{0,40}}\b"
        rf"(?:except|besides|other\s+than)\s+(?:the\s+)?{excluded_pattern}\b",
    )
    return any(re.search(pattern, quote, flags=re.IGNORECASE) for pattern in patterns)


def _other_than_alternative_is_explicit(quote: str, excluded: str) -> bool:
    excluded_tokens = set(re.findall(r"[a-z0-9]+", excluded.lower()))
    for token in re.findall(r"\b[A-Za-z][A-Za-z0-9_-]*\b", str(quote or "")):
        lowered = token.lower()
        if lowered in excluded_tokens:
            continue
        if any(character.isupper() for character in token[1:]) or any(
            character.isdigit() for character in token
        ):
            return True
    explicit_alternative = re.search(
        r"\b(?:another|additional|alternative|different|other)\s+"
        r"([a-z][a-z0-9_-]*)\b",
        str(quote or ""),
        flags=re.IGNORECASE,
    )
    if explicit_alternative is not None:
        return explicit_alternative.group(1).lower() not in excluded_tokens
    causal_alternative = re.search(
        r"\b([a-z][a-z0-9_-]*)\s+(?:can|could|may|might)\s+"
        r"(?:also\s+)?(?:cause|lead|result|contribute)\w*\b",
        str(quote or ""),
        flags=re.IGNORECASE,
    )
    return bool(
        causal_alternative
        and causal_alternative.group(1).lower() not in excluded_tokens
    )
