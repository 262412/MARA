from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from .boolean_authoritative_conflict import (
    conflict_authorities,
    conflict_authority_matches_item,
    conflict_sides_are_complete,
    with_verified_conflict_slots,
)
from .evidence_alias_lookup import unambiguous_evidence_alias_lookup
from .evidence_schema import EvidenceBundle
from .qasper_answer_relation import resolve_qasper_answer_relation
from .query_plan_schema import QueryPlan
from .typed_proposition_authority_atoms import (
    conflict_slot_bindings as _conflict_slot_bindings,
)
from .typed_proposition_authority_atoms import exact_boolean_atom as _exact_boolean_atom
from .typed_proposition_authority_atoms import (
    free_text_claim_result as _free_text_claim_result,
)
from .typed_proposition_authority_atoms import (
    unknown_claim_result as _unknown_claim_result,
)
from .typed_proposition_authority_schema import TYPED_PROPOSITION_AUTHORITY_CONTRACT
from .typed_proposition_authority_schema import missing_authority as _missing_authority
from .typed_proposition_authority_schema import (
    verified_authority as _verified_authority,
)
from .verification_schema import VerifyDecision


def with_qasper_missing_authority(
    request: Any,
    decision: VerifyDecision,
    *,
    question: str,
    answer: str,
    domain: str,
    reason: str,
) -> VerifyDecision:
    if not _qasper_domain(domain):
        return decision
    required_slot_ids = [slot.slot_id for slot in _required_support_slots(request)]
    authority = _missing_authority(
        _answer_type(request),
        question,
        answer,
        required_slot_ids,
        reason,
    )
    return replace(decision, typed_authority=authority)


def resolve_qasper_authority_transaction(
    request: Any,
    decision: VerifyDecision,
    evidence_bundle: EvidenceBundle,
    *,
    question: str,
    answer: str,
    domain: str,
) -> VerifyDecision | None:
    """Commit one coherent QASPER claim/slot/plan authority projection.

    ``None`` means the request is outside this contract and should retain the
    domain's existing verification path.
    """

    if not _qasper_domain(domain):
        return None
    answer_type = _answer_type(request)
    required_slots = _required_support_slots(request)
    required_slot_ids = [slot.slot_id for slot in required_slots]
    if answer_type == "boolean":
        return _resolve_boolean_transaction(
            request,
            decision,
            evidence_bundle,
            question=question,
            answer=answer,
            required_slots=required_slots,
            required_slot_ids=required_slot_ids,
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


def coherent_authority_failure(
    decision: VerifyDecision,
    reason: str,
    *,
    typed_authority: dict[str, Any] | None = None,
) -> VerifyDecision:
    """Downgrade every semantic projection together when authority fails."""

    claim_results = [_unknown_claim_result(result) for result in decision.claim_results]
    claims = list(decision.claims)
    return replace(
        decision,
        status="unknown",
        reason=f"Typed proposition authority was not established: {reason}.",
        action="abstain",
        unsupported_claims=[],
        unknown_claims=claims,
        verified_citations=[],
        claim_results=claim_results,
        input_answer_polarity="",
        canonical_answer_polarity="",
        semantic_correction_applied=False,
        boolean_authority_status="missing",
        authoritative_evidence_id="",
        authoritative_evidence_ref="",
        authoritative_span_id="",
        authoritative_quote="",
        authoritative_span_start=None,
        authoritative_span_end=None,
        authoritative_canonical_start=None,
        authoritative_canonical_end=None,
        actor="",
        section_scope="",
        relation="",
        object="",
        predicate_arguments=(),
        qualifier="",
        quantifier="",
        verified_support_slot_ids=[],
        authoritative_conflict={},
        typed_authority=deepcopy(typed_authority or {}),
    )


def typed_slot_bindings(decision: VerifyDecision) -> dict[str, tuple[str, ...]]:
    authority = decision.typed_authority
    if not isinstance(authority, dict):
        return {}
    payload = authority.get("slot_bindings")
    if not isinstance(payload, dict):
        return {}
    return {
        str(slot_id): tuple(
            str(value).strip() for value in values or [] if str(value).strip()
        )
        for slot_id, values in payload.items()
        if str(slot_id).strip() and isinstance(values, (list, tuple))
    }


def _resolve_boolean_transaction(
    request: Any,
    decision: VerifyDecision,
    evidence_bundle: EvidenceBundle,
    *,
    question: str,
    answer: str,
    required_slots: list[Any],
    required_slot_ids: list[str],
) -> VerifyDecision:
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
    atom = _exact_boolean_atom(decision, evidence_bundle, question=question)
    if decision.status != "supported" or atom is None or not required_slots:
        reason = (
            "required_support_slot_missing"
            if not required_slots
            else "exact_boolean_authority_missing"
        )
        authority = _missing_authority(
            "boolean", question, answer, required_slot_ids, reason
        )
        return coherent_authority_failure(
            decision,
            reason,
            typed_authority=authority,
        )
    evidence_id = str(atom["evidence_id"])
    bindings: dict[str, tuple[str, ...]] = {
        str(slot.slot_id): (evidence_id,) for slot in required_slots
    }
    state_version = _commit_query_plan(request, bindings, "verified_support")
    authority = _verified_authority(
        "boolean",
        question,
        answer,
        decision.claim_results,
        bindings,
        [atom],
        state="verified_support",
        reason="exact_boolean_proposition",
        canonical_answer_polarity=decision.canonical_answer_polarity,
        query_plan_state_version=state_version,
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
    return replace(
        decision,
        claim_results=claim_results,
        verified_citations=[evidence_id],
        verified_support_slot_ids=slot_ids,
        boolean_authority_status="verified_support",
        typed_authority=authority,
    )


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
    resolution = resolve_qasper_answer_relation(
        question,
        answer,
        list(evidence_bundle.items),
    )
    extension_unverified = len(decision.claim_results) > 1 and any(
        str(result.get("status") or "") != "supported"
        for result in decision.claim_results
    )
    if (
        resolution.state != "verified_support"
        or not resolution.atoms
        or not required_slots
        or extension_unverified
    ):
        reason = (
            "claim_extension_unverified"
            if extension_unverified
            else "required_support_slot_missing"
            if not required_slots
            else resolution.reason
        )
        authority = _missing_authority(
            "free_text", question, answer, required_slot_ids, reason
        )
        return coherent_authority_failure(
            decision,
            reason,
            typed_authority=authority,
        )
    return _commit_free_text_transaction(
        request,
        decision,
        question=question,
        answer=answer,
        required_slots=required_slots,
        atoms=list(resolution.atoms),
        reason=resolution.reason,
    )


def _commit_free_text_transaction(
    request: Any,
    decision: VerifyDecision,
    *,
    question: str,
    answer: str,
    required_slots: list[Any],
    atoms: list[dict[str, Any]],
    reason: str,
) -> VerifyDecision:
    atom = atoms[0]
    evidence_ids = tuple(dict.fromkeys(str(value["evidence_id"]) for value in atoms))
    bindings = {slot.slot_id: evidence_ids for slot in required_slots}
    state_version = _commit_query_plan(request, bindings, "verified_support")
    claims = list(decision.claims) or [str(answer or "").strip()]
    claim_results = [
        _free_text_claim_result(
            decision.claim_results[index]
            if index < len(decision.claim_results)
            else {},
            claim=claim,
            claim_id=f"claim:{index + 1}",
            atom=atoms[min(index, len(atoms) - 1)],
            slot_ids=list(bindings),
        )
        for index, claim in enumerate(claims)
    ]
    authority = _verified_authority(
        "free_text",
        question,
        answer,
        claim_results,
        bindings,
        atoms,
        state="verified_support",
        reason=reason,
        query_plan_state_version=state_version,
    )
    return replace(
        decision,
        status="supported",
        reason="Typed QASPER answer relation is supported.",
        action="generate",
        claims=claims,
        unsupported_claims=[],
        unknown_claims=[],
        verified_citations=list(evidence_ids),
        claim_results=claim_results,
        authoritative_evidence_id=str(atom["evidence_id"]),
        authoritative_evidence_ref=str(atom["evidence_ref"]),
        authoritative_span_id=str(atom["span_id"]),
        authoritative_quote=str(atom["quote"]),
        authoritative_span_start=atom.get("span_start"),
        authoritative_span_end=atom.get("span_end"),
        authoritative_canonical_start=atom.get("canonical_start"),
        authoritative_canonical_end=atom.get("canonical_end"),
        actor=str(atom["actor"]),
        section_scope=str(atom["section_scope"]),
        relation=str(atom["relation"]),
        object=str(atom["object"]),
        predicate_arguments=tuple(atom.get("arguments") or ()),
        qualifier=str(atom["qualifier"]),
        quantifier=str(atom["quantifier"]),
        verified_support_slot_ids=list(bindings),
        typed_authority=authority,
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
        return _conflict_failure(
            decision,
            question,
            answer,
            required_slot_ids,
            "authoritative_conflict_incomplete",
        )
    bindings = _conflict_slot_bindings(required_slots, atoms)
    if set(bindings) != set(required_slot_ids):
        return _conflict_failure(
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


def _conflict_failure(
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
) -> int:
    plan = getattr(request, "query_plan", None)
    if not isinstance(plan, QueryPlan):
        return int(getattr(request, "query_plan_state_version", 0) or 0)
    authoritative = replace(
        plan,
        evidence_slots=tuple(
            replace(slot, status=status, evidence_ids=bindings[slot.slot_id])
            if slot.slot_id in bindings
            else slot
            for slot in plan.evidence_slots
        ),
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


def _answer_type(request: Any) -> str:
    plan = getattr(request, "query_plan", None)
    value = getattr(plan, "answer_type", None) if plan is not None else None
    return str(value or getattr(request, "task_type", "") or "free_text").lower()


def _qasper_domain(domain: str) -> bool:
    normalized = str(domain or "").strip().lower()
    return normalized == "qasper" or normalized.startswith("qasper_")
