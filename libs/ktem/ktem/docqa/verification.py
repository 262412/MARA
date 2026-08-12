from __future__ import annotations

from dataclasses import replace
from typing import Any

from .calculation_claim_verification import calculation_claim_result
from .calculation_evidence_identity import calculation_evidence_lookup
from .claim_clauses import split_claim_clauses
from .claim_support import claim_supported
from .domain_verifiers import normalize_verification_domain
from .evidence import EvidenceBundle
from .evidence_identity import identity_of
from .query_plan_schema import QueryPlan
from .query_planning import request_planning_question
from .verification_evidence_mapping import (
    blocking_verification_slots,
    claim_support_identities_by_claim,
    pending_verification_slots,
    verification_slots,
)
from .verification_logic import VerifiedClaim  # noqa: F401
from .verification_logic import verify_claim  # noqa: F401
from .verification_logic import (
    VerifyDecision,
    _boolean_verification,
    _calculation_verification_results,
    _can_verify_available_evidence,
    _decision_for_claim_results,
    _domain_verification,
    _verification_context,
    _verify_claims,
    normalize_verification_mode,
)
from .verification_slot_support import (
    claim_aware_slot_support,
    enforce_verification_slot_support,
    slot_value,
)


def verify_decision(
    request: Any,
    retrieve_decision: Any,
    evidence_bundle: EvidenceBundle,
    answer: str = "",
) -> VerifyDecision:
    mode = normalize_verification_mode(getattr(request, "verification_mode", None))
    if mode == "off":
        return VerifyDecision(
            mode=mode,
            status="not_requested",
            reason="Verification disabled.",
        )
    if retrieve_decision.status == "not_required":
        return VerifyDecision(
            mode=mode,
            status="not_required",
            reason="Direct route does not require evidence verification.",
        )
    missing_slots = blocking_verification_slots(request, evidence_bundle)
    if missing_slots:
        action = "retry" if retrieve_decision.retry else "abstain"
        return VerifyDecision(
            mode=mode,
            status="not_enough_evidence",
            reason=(
                "Verification-required evidence slots are missing: "
                + ", ".join(missing_slots)
            ),
            action=action,
        )
    prompt, domain, claims = _verification_context(request, answer)
    if retrieve_decision.status != "good" and not _can_verify_available_evidence(
        evidence_bundle,
        claims,
    ):
        action = "retry" if retrieve_decision.retry else "abstain"
        return VerifyDecision(
            mode=mode,
            status="not_enough_evidence",
            reason=f"{mode.title()} verification requested without sufficient evidence.",
            action=action,
        )
    claims, results = _verification_results(
        evidence_bundle,
        answer=answer,
        claims=claims,
        prompt=prompt,
        domain=domain,
        request=request,
    )
    decision = _decision_for_claim_results(
        mode,
        retrieve_decision.status,
        claims,
        results,
        evidence_bundle.items,
        prompt=prompt,
        domain=domain,
    )
    return enforce_verification_slot_support(
        request, decision, evidence_bundle, prompt=prompt, domain=domain
    )


def _verification_results(
    evidence_bundle: EvidenceBundle,
    *,
    answer: str,
    claims: list[str],
    prompt: str,
    domain: str,
    request: Any,
) -> tuple[list[str], list[VerifiedClaim]]:
    calculation_claims = split_claim_clauses(claims) if domain == "finance" else claims
    typed_calculation = calculation_claim_result(
        evidence_bundle, answer, calculation_claims, domain=domain, prompt=prompt
    )
    if typed_calculation is not None:
        return calculation_claims, _calculation_verification_results(
            typed_calculation,
            calculation_claims,
            evidence_bundle.items,
            prompt=prompt,
            domain=domain,
        )
    typed_domain = _domain_verification(
        claims,
        evidence_bundle.items,
        prompt=prompt,
        domain=domain,
    )
    if typed_domain is not None:
        return claims, typed_domain
    typed_boolean = _boolean_verification(
        prompt,
        answer,
        evidence_bundle.items,
        allow_missing_polarity=_request_requires_boolean_authority(request),
    )
    if typed_boolean is not None:
        return typed_boolean
    return claims, _verify_claims(claims, evidence_bundle.items, prompt, domain)


def _request_requires_boolean_authority(request: Any) -> bool:
    plan = getattr(request, "query_plan", None)
    if isinstance(plan, dict):
        answer_type = plan.get("answer_type")
    else:
        answer_type = getattr(plan, "answer_type", None)
    return str(answer_type or getattr(request, "task_type", "")).lower() == "boolean"


def with_verification_evidence(
    bundle: EvidenceBundle,
    decision: VerifyDecision,
    request: Any | None = None,
) -> EvidenceBundle:
    if decision.status not in {"supported", "unsupported", "unknown"}:
        return bundle
    citation_ids = {
        str(citation).strip()
        for citation in decision.verified_citations
        if str(citation).strip()
    }
    lookup = calculation_evidence_lookup(bundle.items)
    verified = []
    seen: set[str] = set()
    for citation_id in citation_ids:
        item = lookup.get(citation_id)
        if item is None:
            continue
        identity = identity_of(item).key
        if identity not in seen:
            seen.add(identity)
            verified.append(item)
    metadata = dict(bundle.metadata)
    metadata["verified_evidence"] = verified
    metadata["verified_claim_support_evidence"] = list(verified)
    metadata["verified_claim_support_by_claim"] = claim_support_identities_by_claim(
        decision.claim_results,
        lookup,
    )
    verified_spans = [
        dict(span)
        for result in decision.claim_results
        for span in result.get("supporting_evidence_spans") or []
        if isinstance(span, dict)
    ]
    if verified_spans:
        metadata["verified_claim_support_spans"] = verified_spans
    if decision.canonical_answer_polarity:
        metadata["boolean_authority"] = _boolean_authority_metadata(decision)
    if request is not None:
        verified_ids = {identity_of(item).key for item in verified}
        reconciled_slots = claim_aware_slot_support(
            request,
            decision,
            bundle,
            prompt=request_planning_question(request),
            domain=normalize_verification_domain(
                getattr(request, "verification_domain", None)
            ),
        )
        metadata["verification_slot_states"] = _verification_slot_states(
            request,
            verified_ids,
            reconciled_slots=reconciled_slots,
        )
        pending_slots = pending_verification_slots(request, bundle)
        if pending_slots:
            metadata["pending_verification_slot_ids"] = pending_slots
        _synchronize_verified_claim_query_plan(
            request,
            metadata,
            decision,
            reconciled_slots,
        )
    metadata["verify_decision"] = decision.as_dict()
    return EvidenceBundle(route=bundle.route, items=bundle.items, metadata=metadata)


def _boolean_authority_metadata(decision: VerifyDecision) -> dict[str, Any]:
    return {
        "status": decision.boolean_authority_status,
        "input_answer_polarity": decision.input_answer_polarity,
        "canonical_answer_polarity": decision.canonical_answer_polarity,
        "semantic_correction_applied": decision.semantic_correction_applied,
        "evidence_id": decision.authoritative_evidence_id,
        "evidence_ref": decision.authoritative_evidence_ref,
        "span_id": decision.authoritative_span_id,
        "quote": decision.authoritative_quote,
        "span_start": decision.authoritative_span_start,
        "span_end": decision.authoritative_span_end,
        "canonical_start": decision.authoritative_canonical_start,
        "canonical_end": decision.authoritative_canonical_end,
        "actor": decision.actor,
        "section_scope": decision.section_scope,
        "relation": decision.relation,
        "object": decision.object,
        "predicate": decision.relation,
        "arguments": list(decision.predicate_arguments),
        "qualifier": decision.qualifier,
        "scope": decision.section_scope,
        "quantifier": decision.quantifier,
    }


def _verification_slot_states(
    request: Any,
    verified_evidence_ids: set[str],
    *,
    reconciled_slots: dict[str, tuple[str, ...]] | None = None,
) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    reconciled_slots = reconciled_slots or {}
    for slot in verification_slots(request):
        slot_id = str(slot_value(slot, "slot_id") or "")
        reconciled_ids = reconciled_slots.get(slot_id, ())
        evidence_ids = (
            list(reconciled_ids)
            if reconciled_ids
            else list(slot_value(slot, "evidence_ids") or ())
        )
        states.append(
            {
                "slot_id": slot_id,
                "status": (
                    "verified_support"
                    if set(evidence_ids) & verified_evidence_ids
                    else str(slot_value(slot, "status") or "missing")
                ),
                "evidence_ids": evidence_ids,
            }
        )
    return states


def _synchronize_verified_claim_query_plan(
    request: Any,
    metadata: dict[str, Any],
    decision: VerifyDecision,
    reconciled_slots: dict[str, tuple[str, ...]],
) -> None:
    plan = getattr(request, "query_plan", None)
    if decision.status != "supported" or not isinstance(plan, QueryPlan):
        return
    verification_support_slots = [
        slot
        for slot in plan.evidence_slots
        if slot.required_for_verification and slot.role == "support"
    ]
    if not verification_support_slots or any(
        not reconciled_slots.get(slot.slot_id) for slot in verification_support_slots
    ):
        return
    authoritative = replace(
        plan,
        evidence_slots=tuple(
            replace(
                slot,
                status="verified_support",
                evidence_ids=reconciled_slots[slot.slot_id],
            )
            if slot in verification_support_slots
            else slot
            for slot in plan.evidence_slots
        ),
    )
    state_version = int(getattr(request, "query_plan_state_version", 0) or 0) + 1
    request.query_plan = authoritative
    request.query_plan_id = authoritative.plan_id
    request.query_plan_state_version = state_version
    payload = authoritative.as_dict()
    payload.update(
        {
            "stage": "verified",
            "state_version": state_version,
            "state_authority": "verified_claim_support.v1",
        }
    )
    metadata["query_plan"] = payload
    metadata["bound_query_plan"] = payload
    metadata["query_plan_id"] = authoritative.plan_id
    metadata["missing_required_slot_count"] = sum(
        slot.required_for_retrieval
        and slot.status not in {"filled", "verified_support"}
        for slot in authoritative.evidence_slots
    )


def verified_citations(
    evidence_bundle: EvidenceBundle,
    *,
    claims: list[str] | None = None,
    prompt: str = "",
    domain: str = "",
) -> list[str]:
    if claims is None:
        return []
    citations: list[str] = []
    for claim in claims:
        supporting_items = [
            item
            for item in evidence_bundle.items
            if claim_supported(claim, [item], prompt=prompt, domain=domain)
        ]
        for item in supporting_items:
            evidence_id = identity_of(item).key
            if evidence_id and evidence_id not in citations:
                citations.append(evidence_id)
    return citations


def _enforce_verification_slot_support(
    request: Any,
    decision: VerifyDecision,
    evidence_bundle: EvidenceBundle | None = None,
    *,
    prompt: str = "",
    domain: str = "",
) -> VerifyDecision:
    return enforce_verification_slot_support(
        request,
        decision,
        evidence_bundle,
        prompt=prompt,
        domain=domain,
    )
