from __future__ import annotations

from collections.abc import Iterable
from typing import AbstractSet, Any

from .qasper_boolean_grounding import resolve_grounded_boolean_conflict
from .qasper_quote_support import resolve_verified_quote_support


def required_authority_audit(
    *,
    required: set[str],
    selected_aliases: Iterable[AbstractSet[str]],
    required_slot_ids: list[str] | None,
    missing_required_slot_ids: list[str] | None,
    missing_required_evidence_ids: list[str] | None,
) -> dict[str, str]:
    selected = list(selected_aliases)
    required_selected = {
        required_id
        for required_id in required
        if any(required_id in aliases for aliases in selected)
    }
    slot_ids = _normalized_values(required_slot_ids)
    missing_slots = _normalized_values(missing_required_slot_ids)
    missing_evidence = _normalized_values(missing_required_evidence_ids)
    for slot_id in missing_slots:
        if slot_id not in slot_ids:
            slot_ids.append(slot_id)
    authority_slot_count = max(0, len(slot_ids) - len(missing_slots))
    coverage = len(required_selected) / len(required) if required else 0.0
    if missing_slots or (slot_ids and not required):
        coverage = 0.0
    applicable = bool(slot_ids or required)
    if not applicable:
        status = "not_applicable"
    elif missing_slots or not required:
        status = "missing_required_evidence"
    elif coverage < 1.0:
        status = "required_evidence_not_selected"
    else:
        status = "complete"
    return {
        "verifier_required_evidence_ids": ",".join(sorted(required)),
        "verifier_required_slot_ids": ",".join(slot_ids),
        "verifier_required_slot_count": str(len(slot_ids)),
        "verifier_required_slot_authority_count": str(
            authority_slot_count if required else 0
        ),
        "verifier_missing_required_slot_ids": ",".join(
            slot_ids if not required else missing_slots
        ),
        "verifier_missing_required_evidence_ids": ",".join(missing_evidence),
        "verifier_required_authority_status": status,
        "verifier_required_evidence_coverage": (
            f"{coverage:.6f}" if applicable else ""
        ),
    }


def required_authority_is_missing(parse_trace: dict[str, str]) -> bool:
    return str(parse_trace.get("verifier_required_authority_status") or "") in {
        "missing_required_evidence",
        "required_evidence_not_selected",
    }


def clear_authority_trace(trace: dict[str, str]) -> None:
    for key in (
        "evidence_ref",
        "authoritative_quote_evidence_id",
        "authoritative_claim_key",
        "authoritative_quote_span_id",
        "bound_support_evidence_ids",
        "final_support_evidence_ids",
        "binding_status",
        "evidence_ref_binding_status",
        "evidence_ref_rebound",
    ):
        trace.pop(key, None)


def resolve_boolean_authority_and_conflict(
    *,
    question: str,
    evidence: str,
    evidence_ref: str,
    quote: str,
    verdict: str,
    reason: str,
    quote_supports_relation: bool,
    evidence_items: list[dict[str, Any]] | None,
    candidate_polarity: str,
    parse_trace: dict[str, str],
    relation_trace: dict[str, str],
) -> tuple[str, bool, str, Any, str, str]:
    (
        verdict,
        quote_supports_relation,
        reason,
        authoritative_support,
    ) = resolve_verified_quote_support(
        question,
        evidence_ref,
        quote,
        verdict,
        reason,
        quote_supports_relation,
        evidence_items,
        alias_mapping=parse_trace.get("verifier_evidence_alias_mapping", ""),
    )
    action, answer, conflict_trace = resolve_grounded_boolean_conflict(
        question,
        evidence,
        candidate_polarity,
        verdict=verdict,
        evidence_items=evidence_items,
        relation_trace=relation_trace,
        authoritative_support=authoritative_support,
    )
    relation_trace.update(conflict_trace)
    return (
        verdict,
        quote_supports_relation,
        reason,
        authoritative_support,
        action,
        answer,
    )


def preserve_semantic_veto(reason: str, quote: str, quote_grounded: bool) -> bool:
    return bool(quote_grounded and quote and reason in _SEMANTIC_VETO_REASONS)


_SEMANTIC_VETO_REASONS = {
    "quantified_object_scope_incomplete",
    "quantified_scope_requires_current_paper_actor",
    "cited_work_does_not_establish_current_paper_claim",
    "language_scope_requires_current_experiment_evidence",
    "english_scope_not_closed",
    "no_non_english_counterexample",
    "current_paper_scope_not_established",
}


def _normalized_values(values: list[str] | None) -> list[str]:
    return list(
        dict.fromkeys(
            str(value).strip() for value in values or [] if str(value).strip()
        )
    )
