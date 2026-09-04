from __future__ import annotations

from dataclasses import replace
from typing import Any

from .domain_verifiers import normalize_verification_domain
from .query_plan_schema import QueryPlan
from .typed_proposition_authority_schema import exact_slot_set_contract
from .verification_schema import VerifyDecision
from .visual_evidence_authority import (
    TYPED_VISUAL_EVIDENCE_PATH_CONTRACT,
    validated_visual_answer_authority,
)
from .visual_time_series import validated_visual_time_series_authority


def visual_verification_decision(
    request: Any,
    retrieve_decision: Any,
    evidence_bundle: Any,
    *,
    mode: str,
    answer: str,
) -> VerifyDecision | None:
    domain = normalize_verification_domain(
        getattr(request, "verification_domain", None)
    )
    if retrieve_decision.status != "good" or not (
        domain == "slidevqa" or _is_mmdoc_domain(domain)
    ):
        return None
    time_series_authority = validated_visual_time_series_authority(
        request,
        evidence_bundle,
        answer,
    )
    if time_series_authority is not None:
        return _typed_visual_decision(
            request,
            time_series_authority,
            time_series_authority["typed_visual_path"],
            mode=mode,
        )
    authority = validated_visual_answer_authority(evidence_bundle, answer)
    if authority is None:
        return None
    typed_path = authority.get("typed_visual_path")
    if _is_mmdoc_domain(domain):
        return _typed_visual_decision(
            request,
            authority,
            typed_path,
            mode=mode,
        )
    evidence_ids = list(authority["evidence_ids"])
    claim = str(authority["answer"]).strip()
    claim_result = {
        "claim_id": "claim:1",
        "claim": claim,
        "status": "supported",
        "supporting_evidence_ids": evidence_ids,
        "authority_status": "visual_page",
        "verified_slot_state": "verified_support",
    }
    return VerifyDecision(
        mode=mode,
        status="supported",
        reason="Visual answer is bound to selected page-image evidence.",
        action="generate",
        claims=[claim],
        verified_citations=evidence_ids,
        claim_results=[claim_result],
    )


def _typed_visual_decision(
    request: Any,
    authority: dict[str, Any],
    typed_path: Any,
    *,
    mode: str,
) -> VerifyDecision | None:
    if not isinstance(typed_path, dict):
        return None
    required_slot_ids = _slot_ids(typed_path.get("required_slot_ids"))
    verified_slot_ids = _slot_ids(typed_path.get("verified_support_slot_ids"))
    bindings = typed_path.get("slot_bindings")
    if (
        not isinstance(bindings, dict)
        or not exact_slot_set_contract(
            required_slot_ids,
            verified_slot_ids,
            bindings,
        )
        or any(not values for values in bindings.values())
    ):
        return None
    state_version = _commit_visual_query_plan(request, bindings)
    evidence_ids = list(
        dict.fromkeys(
            str(evidence_id).strip()
            for values in bindings.values()
            for evidence_id in values or []
            if str(evidence_id).strip()
        )
    )
    typed_authority = {
        "contract_id": TYPED_VISUAL_EVIDENCE_PATH_CONTRACT,
        "state": "verified_support",
        "required_slot_ids": required_slot_ids,
        "verified_support_slot_ids": required_slot_ids,
        "slot_bindings": {
            str(slot_id): list(values) for slot_id, values in bindings.items()
        },
        "query_plan_state_version": state_version,
        "authority_evidence_ids": evidence_ids,
    }
    claim = str(authority["answer"]).strip()
    return VerifyDecision(
        mode=mode,
        status="supported",
        reason="Visual answer is bound to typed page-to-operand evidence.",
        action="generate",
        claims=[claim],
        verified_citations=evidence_ids,
        claim_results=[
            {
                "claim_id": "claim:1",
                "claim": claim,
                "status": "supported",
                "supporting_evidence_ids": evidence_ids,
                "authority_status": "typed_visual",
                "verified_slot_state": "verified_support",
                "verified_support_slot_ids": required_slot_ids,
            }
        ],
        verified_support_slot_ids=required_slot_ids,
        typed_authority=typed_authority,
    )


def _commit_visual_query_plan(
    request: Any,
    bindings: dict[str, Any],
) -> int:
    plan = getattr(request, "query_plan", None)
    if not isinstance(plan, QueryPlan):
        return int(getattr(request, "query_plan_state_version", 0) or 0)
    authoritative = replace(
        plan,
        evidence_slots=tuple(
            (
                replace(
                    slot,
                    status="verified_support",
                    evidence_ids=tuple(bindings[slot.slot_id]),
                )
                if slot.slot_id in bindings
                else slot
            )
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


def _is_mmdoc_domain(domain: str) -> bool:
    normalized = str(domain or "").strip().lower()
    return normalized in {"mmdoc", "mmdocrag", "multimodal_doc_qa"} or (
        "mmdoc" in normalized
    )


def _slot_ids(values: Any) -> list[str]:
    return [str(value).strip() for value in values or [] if str(value).strip()]
