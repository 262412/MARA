from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .qasper_authority import (
    clear_authority_trace,
    preserve_semantic_veto,
    required_authority_is_missing,
    resolve_boolean_authority_and_conflict,
)
from .qasper_boolean_grounding import ground_boolean_verdict
from .qasper_quote_support import (
    authoritative_quote_binding_trace,
    evidence_ref_for_quote,
)


@dataclass(frozen=True)
class BooleanAdjudication:
    answer: str
    verdict: str
    action: str
    evidence_ref: str
    quote: str
    quote_grounded: bool
    quote_supports_relation: bool
    relation_trace: dict[str, str]
    raw_verdict: str
    reason: str


def adjudicate_boolean(
    *,
    question: str,
    evidence: str,
    evidence_items: list[dict[str, Any]] | None,
    candidate_polarity: str,
    verdict: str,
    evidence_ref: str,
    quote: str,
    parse_trace: dict[str, str],
) -> BooleanAdjudication:
    state, authoritative_support = _grounded_authority_state(
        question=question,
        evidence=evidence,
        evidence_items=evidence_items,
        candidate_polarity=candidate_polarity,
        verdict=verdict,
        evidence_ref=evidence_ref,
        quote=quote,
        parse_trace=parse_trace,
    )
    finalized = _finalize_boolean_authority(
        question=question,
        state=state,
        evidence_items=evidence_items,
        authoritative_support=authoritative_support,
        alias_mapping=parse_trace.get("verifier_evidence_alias_mapping", ""),
        parse_trace=parse_trace,
    )
    if required_authority_is_missing(parse_trace):
        return _missing_required_authority(finalized)
    return finalized


def _grounded_authority_state(
    *,
    question: str,
    evidence: str,
    evidence_items: list[dict[str, Any]] | None,
    candidate_polarity: str,
    verdict: str,
    evidence_ref: str,
    quote: str,
    parse_trace: dict[str, str],
) -> tuple[BooleanAdjudication, Any]:
    (
        verdict,
        raw_verdict,
        quote_grounded,
        quote_supports_relation,
        reason,
        relation_trace,
    ) = ground_boolean_verdict(
        question=question,
        evidence=evidence,
        verdict=verdict,
        quote=quote,
        evidence_items=evidence_items,
    )
    (
        verdict,
        quote_supports_relation,
        reason,
        authoritative_support,
        action,
        answer,
    ) = resolve_boolean_authority_and_conflict(
        question=question,
        evidence=evidence,
        evidence_ref=evidence_ref,
        quote=quote,
        verdict=verdict,
        reason=reason,
        quote_supports_relation=quote_supports_relation,
        evidence_items=evidence_items,
        candidate_polarity=candidate_polarity,
        parse_trace=parse_trace,
        relation_trace=relation_trace,
    )
    if (
        authoritative_support is not None
        and parse_trace.get("quote_ref_validation_status") == "evidence_ref_rebound"
    ):
        authoritative_support = replace(
            authoritative_support,
            binding_status="evidence_ref_rebound",
        )
    return (
        BooleanAdjudication(
            answer=answer,
            verdict=verdict,
            action=action,
            evidence_ref=evidence_ref,
            quote=quote,
            quote_grounded=quote_grounded,
            quote_supports_relation=quote_supports_relation,
            relation_trace=relation_trace,
            raw_verdict=raw_verdict,
            reason=reason,
        ),
        authoritative_support,
    )


def _finalize_boolean_authority(
    *,
    question: str,
    state: BooleanAdjudication,
    evidence_items: list[dict[str, Any]] | None,
    authoritative_support: Any,
    alias_mapping: str,
    parse_trace: dict[str, str],
) -> BooleanAdjudication:
    selected_answer = state.answer if state.answer in {"yes", "no"} else ""
    if selected_answer and authoritative_support is not None:
        binding_trace = authoritative_quote_binding_trace(
            question,
            selected_answer,
            evidence_items or [],
            authoritative_support,
        )
        if not str(parse_trace.get("verifier_required_slot_ids") or "").strip():
            binding_trace.update(
                {
                    "verifier_required_evidence_ids": (
                        authoritative_support.evidence_id
                    ),
                    "verifier_required_slot_ids": "support:boolean_proposition",
                    "verifier_required_slot_count": "1",
                    "verifier_required_slot_authority_count": "1",
                    "verifier_missing_required_slot_ids": "",
                    "verifier_missing_required_evidence_ids": "",
                    "verifier_required_authority_status": "complete",
                    "verifier_required_evidence_coverage": "1.000000",
                }
            )
        state.relation_trace.update(binding_trace)
    if not selected_answer or authoritative_support is None:
        if preserve_semantic_veto(
            state.reason,
            state.quote,
            state.quote_grounded,
        ):
            rebound_ref = evidence_ref_for_quote(
                state.quote,
                evidence_items or [],
                alias_mapping,
            )
            evidence_ref = rebound_ref or state.evidence_ref
            if evidence_ref and state.quote:
                return replace(
                    state,
                    verdict="insufficient_evidence",
                    evidence_ref=evidence_ref,
                    quote_grounded=True,
                    quote_supports_relation=False,
                )
        return replace(
            state,
            verdict="insufficient_evidence",
            evidence_ref="",
            quote="",
            quote_grounded=False,
            quote_supports_relation=False,
        )
    evidence_ref = authoritative_support.evidence_ref or state.evidence_ref
    return replace(state, evidence_ref=evidence_ref)


def _missing_required_authority(
    state: BooleanAdjudication,
) -> BooleanAdjudication:
    clear_authority_trace(state.relation_trace)
    return replace(
        state,
        answer="unanswerable",
        verdict="insufficient_evidence",
        action="abstained_missing_required_evidence",
        evidence_ref="",
        quote="",
        quote_grounded=False,
        quote_supports_relation=False,
        reason="missing_required_evidence_authority",
    )
