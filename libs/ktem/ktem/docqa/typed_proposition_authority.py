from __future__ import annotations

from dataclasses import replace
from typing import Any

from .boolean_authoritative_conflict import (
    conflict_authorities,
    conflict_authority_matches_item,
    conflict_sides_are_complete,
    with_verified_conflict_slots,
)
from .boolean_authority_schema import SEMANTIC_EVIDENCE_SET_RULE
from .boolean_conjunction import derivation_support_group_constraint
from .evidence_alias_lookup import unambiguous_evidence_alias_lookup
from .evidence_schema import EvidenceBundle
from .layered_free_text_authority import resolve_layered_free_text_transaction
from .query_plan_schema import QueryPlan
from .semantic_evidence_set_plan_projection import (
    semantic_authority_plan_projection_from_decision,
)
from .typed_proposition_authority_atoms import (
    bound_boolean_derivations as _bound_boolean_derivations,
)
from .typed_proposition_authority_atoms import (
    conflict_slot_bindings as _conflict_slot_bindings,
)
from .typed_proposition_authority_atoms import (
    exact_boolean_atoms as _exact_boolean_atoms,
)
from .typed_proposition_authority_failure import coherent_authority_failure
from .typed_proposition_authority_missing import (
    with_missing_boolean_authority,
    with_qasper_missing_authority,
)
from .typed_proposition_authority_schema import TYPED_PROPOSITION_AUTHORITY_CONTRACT
from .typed_proposition_authority_schema import (
    has_composite_boolean_authority as _has_composite_boolean_authority,
)
from .typed_proposition_authority_schema import missing_authority as _missing_authority
from .typed_proposition_authority_schema import planned_answer_type as _answer_type
from .typed_proposition_authority_schema import (
    qasper_authority_domain as _qasper_domain,
)
from .typed_proposition_authority_schema import (
    verified_authority as _verified_authority,
)
from .typed_proposition_authority_slots import (
    boolean_slot_bindings as _boolean_slot_bindings,
)
from .verification_schema import VerifyDecision

__all__ = [
    "with_missing_boolean_authority",
    "with_qasper_missing_authority",
]


def resolve_typed_proposition_authority_transaction(
    request: Any,
    decision: VerifyDecision,
    evidence_bundle: EvidenceBundle,
    *,
    question: str,
    answer: str,
    domain: str,
) -> VerifyDecision | None:
    """Commit typed authority; non-QASPER domains opt in for composite proofs."""

    answer_type = _answer_type(request)
    if not _qasper_domain(domain) and not (
        answer_type == "boolean" and _has_composite_boolean_authority(decision)
    ):
        return None
    required_slots = _required_support_slots(request)
    required_slot_ids = [slot.slot_id for slot in required_slots]
    if answer_type == "boolean":
        if decision.status == "verified_conflict":
            return _resolve_conflict_transaction(
                request,
                decision,
                evidence_bundle,
                question=question,
                answer=answer,
                required_slots=required_slots,
                required_slot_ids=required_slot_ids,
            )
        return _resolve_boolean_transaction(
            request,
            decision,
            evidence_bundle,
            question=question,
            answer=answer,
            required_slots=required_slots,
            required_slot_ids=required_slot_ids,
            require_canonical_plan=_qasper_domain(domain),
        )
    return _resolve_free_text_transaction(
        request,
        decision,
        evidence_bundle,
        question=question,
        answer=answer,
        required_slots=required_slots,
        required_slot_ids=required_slot_ids,
    )


resolve_qasper_authority_transaction = resolve_typed_proposition_authority_transaction


def _resolve_boolean_transaction(
    request: Any,
    decision: VerifyDecision,
    evidence_bundle: EvidenceBundle,
    *,
    question: str,
    answer: str,
    required_slots: list[Any],
    required_slot_ids: list[str],
    require_canonical_plan: bool,
) -> VerifyDecision:
    canonical_plan_projection = None
    if require_canonical_plan:
        (
            canonical_plan_projection,
            projection_reason,
        ) = semantic_authority_plan_projection_from_decision(
            question,
            evidence_bundle,
            decision,
        )
        if projection_reason:
            return _boolean_failure(
                decision,
                question,
                answer,
                required_slot_ids,
                projection_reason,
            )
    atoms = _exact_boolean_atoms(
        decision,
        evidence_bundle,
        question=question,
        canonical_plan_projection=canonical_plan_projection,
    )
    derivations = _bound_boolean_derivations(
        decision,
        atoms,
        question=question,
        canonical_plan_projection=canonical_plan_projection,
    )
    composite_expected = _has_composite_boolean_authority(decision)
    if decision.status != "supported" or not atoms or not required_slots:
        reason = (
            "required_support_slot_missing"
            if not required_slots
            else "exact_boolean_authority_missing"
        )
        return _boolean_failure(decision, question, answer, required_slot_ids, reason)
    if composite_expected and not derivations:
        reason = "boolean_authority_derivation_incomplete"
        return _boolean_failure(decision, question, answer, required_slot_ids, reason)
    bindings, slot_ref_bindings, selected_atoms = _boolean_slot_bindings(
        request,
        required_slots,
        atoms,
        derivations,
        canonical_plan_projection=canonical_plan_projection,
    )
    if bindings is None or slot_ref_bindings is None or selected_atoms is None:
        reason = "required_support_slot_binding_incomplete"
        return _boolean_failure(decision, question, answer, required_slot_ids, reason)
    return _commit_boolean_transaction(
        request,
        decision,
        question=question,
        answer=answer,
        required_slot_ids=required_slot_ids,
        bindings=bindings,
        slot_ref_bindings=slot_ref_bindings,
        atoms=selected_atoms,
        derivations=derivations,
    )


def _commit_boolean_transaction(
    request: Any,
    decision: VerifyDecision,
    *,
    question: str,
    answer: str,
    required_slot_ids: list[str],
    bindings: dict[str, tuple[str, ...]],
    slot_ref_bindings: dict[str, tuple[str, ...]],
    atoms: list[dict[str, Any]],
    derivations: list[dict[str, Any]],
) -> VerifyDecision:
    state_version = _commit_query_plan(
        request,
        bindings,
        "verified_support",
        authority_derivations=derivations,
    )
    authority = _verified_authority(
        "boolean",
        question,
        answer,
        decision.claim_results,
        bindings,
        atoms,
        state="verified_support",
        reason=_boolean_authority_reason(derivations),
        canonical_answer_polarity=decision.canonical_answer_polarity,
        query_plan_state_version=state_version,
        required_slot_ids=required_slot_ids,
        slot_ref_bindings=slot_ref_bindings,
        authority_derivations=derivations,
        selected_derivation_id=decision.selected_derivation_id,
    )
    slot_ids = list(bindings)
    claim_results = [
        {
            **result,
            "verified_slot_state": (
                "verified_support"
                if str(result.get("status") or "") == "supported"
                else str(result.get("verified_slot_state") or "")
            ),
            "verified_support_slot_ids": slot_ids,
            "typed_authority_contract": TYPED_PROPOSITION_AUTHORITY_CONTRACT,
        }
        for result in decision.claim_results
    ]
    evidence_ids = list(
        dict.fromkeys(value for ids in bindings.values() for value in ids)
    )
    return replace(
        decision,
        claim_results=claim_results,
        verified_citations=evidence_ids,
        verified_support_slot_ids=slot_ids,
        boolean_authority_status="verified_support",
        typed_authority=authority,
    )


def _boolean_authority_reason(derivations: list[dict[str, Any]]) -> str:
    if not derivations:
        return "exact_boolean_proposition"
    if str(derivations[0].get("rule_id") or "") == SEMANTIC_EVIDENCE_SET_RULE:
        return "semantic_evidence_set_proposition"
    return "composite_boolean_proposition"


def _resolve_free_text_transaction(
    request: Any,
    decision: VerifyDecision,
    evidence_bundle: EvidenceBundle,
    *,
    question: str,
    answer: str,
    required_slots: list[Any],
    required_slot_ids: list[str],
) -> VerifyDecision:
    return resolve_layered_free_text_transaction(
        request,
        decision,
        evidence_bundle,
        question=question,
        answer=answer,
        required_slots=required_slots,
        required_slot_ids=required_slot_ids,
        commit_query_plan=_commit_query_plan,
    )


def _resolve_conflict_transaction(
    request: Any,
    decision: VerifyDecision,
    evidence_bundle: EvidenceBundle,
    *,
    question: str,
    answer: str,
    required_slots: list[Any],
    required_slot_ids: list[str],
) -> VerifyDecision:
    conflict = decision.authoritative_conflict
    lookup = unambiguous_evidence_alias_lookup(evidence_bundle.items)
    atoms = (
        conflict_authorities(conflict) if conflict_sides_are_complete(conflict) else []
    )
    if (
        not atoms
        or not required_slots
        or any(
            (item := lookup.get(str(atom.get("evidence_id") or ""))) is None
            or not conflict_authority_matches_item(atom, item)
            for atom in atoms
        )
    ):
        return _boolean_failure(
            decision,
            question,
            answer,
            required_slot_ids,
            "authoritative_conflict_incomplete",
        )
    bindings = _conflict_slot_bindings(required_slots, atoms)
    if set(bindings) != set(required_slot_ids):
        return _boolean_failure(
            decision,
            question,
            answer,
            required_slot_ids,
            "authoritative_conflict_slot_binding_incomplete",
        )
    return _commit_conflict_transaction(
        request,
        decision,
        question=question,
        answer=answer,
        bindings=bindings,
        atoms=atoms,
    )


def _commit_conflict_transaction(
    request: Any,
    decision: VerifyDecision,
    *,
    question: str,
    answer: str,
    bindings: dict[str, tuple[str, ...]],
    atoms: list[dict[str, Any]],
) -> VerifyDecision:
    conflict = decision.authoritative_conflict
    conflict = with_verified_conflict_slots(conflict, bindings)
    state_version = _commit_query_plan(request, bindings, "verified_conflict")
    authority = _verified_authority(
        "boolean",
        question,
        answer,
        decision.claim_results,
        bindings,
        atoms,
        state="verified_conflict",
        reason="authoritative_conflict_abstention",
        query_plan_state_version=state_version,
        required_slot_ids=list(bindings),
    )
    slot_ids = list(bindings)
    claim_results = [
        {
            **result,
            "authority_status": (
                "verified_conflict"
                if result.get("authoritative_conflict")
                else str(result.get("authority_status") or "")
            ),
            "authoritative_conflict": (
                conflict if result.get("authoritative_conflict") else {}
            ),
            "verified_slot_state": (
                "verified_conflict"
                if result.get("authoritative_conflict")
                else str(result.get("verified_slot_state") or "")
            ),
            "verified_support_slot_ids": slot_ids,
            "typed_authority_contract": TYPED_PROPOSITION_AUTHORITY_CONTRACT,
        }
        for result in decision.claim_results
    ]
    return replace(
        decision,
        claim_results=claim_results,
        verified_citations=[],
        verified_support_slot_ids=slot_ids,
        boolean_authority_status="verified_conflict",
        authoritative_conflict=conflict,
        typed_authority=authority,
    )


def _boolean_failure(
    decision: VerifyDecision,
    question: str,
    answer: str,
    required_slot_ids: list[str],
    reason: str,
) -> VerifyDecision:
    authority = _missing_authority(
        "boolean", question, answer, required_slot_ids, reason
    )
    return coherent_authority_failure(
        decision,
        reason,
        typed_authority=authority,
    )


def _commit_query_plan(
    request: Any,
    bindings: dict[str, tuple[str, ...]],
    status: str,
    *,
    authority_derivations: list[dict[str, Any]] | None = None,
) -> int:
    plan = getattr(request, "query_plan", None)
    if not isinstance(plan, QueryPlan):
        return int(getattr(request, "query_plan_state_version", 0) or 0)
    constraints = dict(plan.constraints)
    if authority_derivations:
        constraints["boolean_support_group"] = derivation_support_group_constraint(
            authority_derivations[0],
            constraints.get("boolean_support_group"),
        )
    authoritative = replace(
        plan,
        evidence_slots=tuple(
            (
                replace(slot, status=status, evidence_ids=bindings[slot.slot_id])
                if slot.slot_id in bindings
                else slot
            )
            for slot in plan.evidence_slots
        ),
        constraints=constraints,
    )
    current_version = int(getattr(request, "query_plan_state_version", 0) or 0)
    if authoritative == plan:
        return current_version
    state_version = current_version + 1
    request.query_plan = authoritative
    request.query_plan_id = authoritative.plan_id
    request.query_plan_state_version = state_version
    return state_version


def _required_support_slots(request: Any) -> list[Any]:
    plan = getattr(request, "query_plan", None)
    if not isinstance(plan, QueryPlan):
        return []
    return [
        slot
        for slot in plan.evidence_slots
        if slot.required_for_verification and slot.role == "support"
    ]
