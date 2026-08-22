from __future__ import annotations

from typing import Any

from .boolean_verification_projection import project_boolean_assessment
from .domain_verifiers import normalize_verification_domain
from .evidence import EvidenceBundle
from .query_planning import request_planning_question
from .semantic_evidence_set_authority import (
    PropositionVerifier,
    semantic_evidence_set_claim_authority,
)
from .typed_proposition_authority import resolve_typed_proposition_authority_transaction
from .verification_logic import (
    VerifiedClaim,
    VerifyDecision,
    _boolean_verification,
    _decision_for_claim_results,
)


def boolean_authority_required(request: Any) -> bool:
    plan = getattr(request, "query_plan", None)
    answer_type = (
        plan.get("answer_type")
        if isinstance(plan, dict)
        else getattr(plan, "answer_type", None)
    )
    return str(answer_type or getattr(request, "task_type", "")).lower() == "boolean"


def verified_boolean_candidate_decision(
    request: Any,
    retrieve_decision: Any,
    evidence_bundle: EvidenceBundle,
    *,
    answer: str,
    mode: str,
    proposition_verifier: PropositionVerifier | None,
) -> VerifyDecision | None:
    if not boolean_authority_required(request) or not evidence_bundle.items:
        return None
    prompt = request_planning_question(request)
    typed_boolean = _boolean_verification(
        prompt,
        answer,
        evidence_bundle.items,
        allow_missing_polarity=True,
    )
    if typed_boolean is None:
        return None
    semantic = semantic_boolean_verification(
        request,
        prompt,
        answer,
        evidence_bundle,
        typed_boolean,
        proposition_verifier,
    )
    claims, results = semantic or typed_boolean
    domain = normalize_verification_domain(
        getattr(request, "verification_domain", None)
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
    typed = resolve_typed_proposition_authority_transaction(
        request,
        decision,
        evidence_bundle,
        question=prompt,
        answer=answer,
        domain=domain,
    )
    if typed is None or typed.status not in {"supported", "verified_conflict"}:
        return None
    return typed


def semantic_boolean_verification(
    request: Any,
    prompt: str,
    answer: str,
    evidence_bundle: EvidenceBundle,
    deterministic: tuple[list[str], list[VerifiedClaim]],
    verifier: PropositionVerifier | None,
) -> tuple[list[str], list[VerifiedClaim]] | None:
    if verifier is None or any(
        result.status != "unknown" for result in deterministic[1]
    ):
        return None
    assessment = semantic_evidence_set_claim_authority(
        request,
        prompt,
        answer,
        evidence_bundle,
        verifier,
    )
    return project_boolean_assessment(assessment) if assessment is not None else None
