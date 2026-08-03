from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ktem.docqa.boolean_proposition_evidence import (
    boolean_proposition_binding_trace,
    classify_boolean_evidence_candidates,
)
from ktem.docqa.evidence_identity import identity_of

from .qasper_boolean_scope import evidence_item_text


@dataclass(frozen=True)
class AuthoritativeQuoteSupport:
    evidence_id: str
    span_id: str
    claim_key: tuple[str, ...]
    polarity: str


def parse_boolean_verdict(answer: str) -> tuple[str, str]:
    try:
        payload = json.loads(str(answer or ""))
    except json.JSONDecodeError:
        return "", ""
    if not isinstance(payload, dict):
        return "", ""
    value = str(payload.get("verdict") or "")
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
    return (value, quote) if value in allowed else ("", "")


def resolve_verified_quote_support(
    question: str,
    quote: str,
    verdict: str,
    reason: str,
    quote_supports_relation: bool,
    evidence_items: list[dict[str, Any]] | None,
) -> tuple[str, bool, str, AuthoritativeQuoteSupport | None]:
    support = None
    if verdict in {"yes", "no"} and reason == "grounded_complete_proposition":
        support = resolve_authoritative_quote_support(
            question,
            quote,
            verdict,
            evidence_items,
        )
        if evidence_items is not None and support is None:
            return "insufficient_evidence", False, "quote_identity_unresolved", None
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
            "authoritative_quote_span_id": support.span_id,
            "bound_support_evidence_ids": [support.evidence_id],
            "final_support_evidence_ids": [support.evidence_id],
            "binding_status": "verified_support",
        }
    )
    return trace


def resolve_authoritative_quote_support(
    question: str,
    quote: str,
    polarity: str,
    evidence_items: list[dict[str, Any]] | None,
) -> AuthoritativeQuoteSupport | None:
    if evidence_items is None:
        return None
    normalized_quote = " ".join(str(quote or "").lower().split())
    if not normalized_quote:
        return None
    matches: dict[str, dict[str, Any]] = {}
    for item in evidence_items:
        normalized_text = " ".join(evidence_item_text(item).lower().split())
        if normalized_quote in normalized_text:
            matches[identity_of(item).key] = item
    if len(matches) != 1:
        return None
    evidence_id, item = next(iter(matches.items()))
    text = evidence_item_text(item)
    quote_pattern = r"\s+".join(
        re.escape(part) for part in str(quote or "").strip().split()
    )
    span_match = re.search(quote_pattern, text, flags=re.IGNORECASE)
    if span_match is None:
        return None
    quote_item = {
        **item,
        "text": span_match.group(0),
        "ocr_text": "",
        "vlm_text": "",
        "caption": "",
    }
    assessments = classify_boolean_evidence_candidates(question, polarity, quote_item)
    if not assessments:
        return None
    assessment = max(
        assessments,
        key=lambda value: (
            value.relation_score * value.object_score,
            value.object_score,
        ),
    )
    return AuthoritativeQuoteSupport(
        evidence_id=evidence_id,
        span_id=f"{evidence_id}#quote:{span_match.start()}:{span_match.end()}",
        claim_key=assessment.proposition.claim_key,
        polarity=polarity,
    )
