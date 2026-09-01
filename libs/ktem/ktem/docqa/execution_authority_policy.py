from __future__ import annotations

from typing import Any

from .boolean_authoritative_conflict import authoritative_conflict_complete
from .controller import VerifyDecision
from .query_planning import ensure_request_query_plan
from .typed_proposition_authority import TYPED_PROPOSITION_AUTHORITY_CONTRACT


def required_typed_authority_missing(
    request: Any,
    verify_decision: VerifyDecision,
) -> bool:
    if verify_decision.mode == "off" or verify_decision.status == "not_requested":
        return False
    if (
        verify_decision.candidate_label == "unanswerable"
        and verify_decision.verifier_candidate_status == "supported"
        and verify_decision.replacement_candidate_allowed is False
    ):
        return False
    plan = ensure_request_query_plan(request)
    typed_required = plan.answer_type == "boolean" or any(
        slot.required_for_verification
        and str(slot.statement_kind or "").lower()
        in {"answer_relation", "boolean_proposition"}
        for slot in plan.evidence_slots
    )
    if not typed_required:
        return False
    typed = verify_decision.typed_authority
    if typed.get("contract_id") == TYPED_PROPOSITION_AUTHORITY_CONTRACT:
        return _typed_authority_missing(verify_decision, typed)
    if verify_decision.status == "verified_conflict":
        return not authoritative_conflict_complete(
            verify_decision.authoritative_conflict
        )
    identity_complete = bool(
        verify_decision.authoritative_evidence_id
        and verify_decision.authoritative_evidence_ref
        and verify_decision.authoritative_quote
    )
    if plan.answer_type == "boolean":
        return not (
            verify_decision.status == "supported"
            and verify_decision.canonical_answer_polarity in {"yes", "no"}
            and identity_complete
        )
    return not (verify_decision.status == "supported" and identity_complete)


def _typed_authority_missing(
    verify_decision: VerifyDecision,
    typed: dict[str, Any],
) -> bool:
    state = str(typed.get("state") or "")
    required = {
        str(value).strip()
        for value in typed.get("required_slot_ids") or []
        if str(value).strip()
    }
    verified = {
        str(value).strip()
        for value in typed.get("verified_slot_ids") or []
        if str(value).strip()
    }
    atoms = [
        atom for atom in typed.get("authority_atoms") or [] if isinstance(atom, dict)
    ]
    if state == "verified_conflict":
        return not authoritative_conflict_complete(
            verify_decision.authoritative_conflict
        )
    return not (
        verify_decision.status == "supported"
        and state == "verified_support"
        and required
        and required == verified
        and atoms
        and all(
            str(atom.get("evidence_id") or "")
            and str(atom.get("evidence_ref") or "")
            and str(atom.get("quote") or "")
            for atom in atoms
        )
    )
