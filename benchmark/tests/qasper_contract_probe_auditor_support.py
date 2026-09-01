from __future__ import annotations

import hashlib
import re
from typing import Any


def controlled_auditor_premise_texts(
    proposal: dict[str, Any],
) -> tuple[tuple[str, str], ...] | None:
    spans = _controlled_evidence_spans(proposal)
    premises = proposal.get("premises")
    if not spans or not isinstance(premises, list) or not premises:
        return None
    resolved: list[tuple[str, str]] = []
    for premise in premises:
        if not isinstance(premise, dict):
            return None
        quote_ref = str(premise.get("frozen_span_ref") or "")
        fragment_ref = str(premise.get("proposition_fragment_ref") or "")
        quote = spans.get(quote_ref, "")
        fragment = spans.get(fragment_ref, "")
        if not _controlled_premise_refs_valid(premise, quote_ref, quote) or premise.get(
            "proposition_fragment_digest"
        ) != _text_digest(fragment):
            return None
        resolved.append((quote, fragment))
    return tuple(resolved)


def _controlled_evidence_spans(proposal: dict[str, Any]) -> dict[str, str]:
    serialization = proposal.get("evidence_serialization")
    if not isinstance(serialization, dict) or serialization.get("contract_id") != (
        "semantic_auditor_controlled_evidence.v1"
    ):
        return {}
    spans = proposal.get("frozen_evidence_spans")
    if not isinstance(spans, list) or not spans:
        return {}
    controlled: dict[str, str] = {}
    for span in spans:
        if not isinstance(span, dict):
            return {}
        evidence_ref = str(span.get("evidence_ref") or "")
        text = str(span.get("text") or "")
        if (
            not evidence_ref
            or evidence_ref in controlled
            or span.get("text_digest") != _text_digest(text)
        ):
            return {}
        controlled[evidence_ref] = text
    return controlled


def _controlled_premise_refs_valid(
    premise: dict[str, Any],
    quote_ref: str,
    quote: str,
) -> bool:
    if not quote_ref or premise.get("frozen_span_digest") != _text_digest(quote):
        return False
    contributions = premise.get("local_proposition_slot_contributions")
    if not isinstance(contributions, dict) or not contributions:
        return False
    for contribution in contributions.values():
        if not _controlled_contribution_valid(contribution, quote_ref, quote):
            return False
    alignment = premise.get("semantic_alignment")
    return bool(
        isinstance(alignment, dict)
        and alignment.get("source_span_ref") == quote_ref
        and _digest_valid(alignment.get("alignment_digest"))
    )


def _controlled_contribution_valid(
    contribution: Any,
    quote_ref: str,
    quote: str,
) -> bool:
    if (
        not isinstance(contribution, dict)
        or contribution.get("source_span_ref") != quote_ref
        or "text" in contribution
        or not _digest_valid(contribution.get("text_digest"))
    ):
        return False
    start = contribution.get("relative_start")
    end = contribution.get("relative_end")
    if not isinstance(start, int) or not isinstance(end, int):
        return False
    return 0 <= start <= end <= len(quote) and (
        _text_digest(quote[start:end]) == contribution["text_digest"]
    )


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _digest_valid(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))
