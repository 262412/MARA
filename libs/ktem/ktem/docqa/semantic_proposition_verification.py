from __future__ import annotations

from typing import Any

from .boolean_candidate_authority import (
    candidate_bound_boolean_claim_authority,
    structured_boolean_candidate_label,
)
from .candidate_verification_policy import finish_candidate_decision
from .boolean_verification_projection import project_boolean_assessment
from .domain_verifiers import normalize_verification_domain
from .evidence import EvidenceBundle
from .query_planning import request_planning_question
from .semantic_evidence_set_authority import (
    PropositionVerifier,
    semantic_evidence_set_claim_authority,
)
from .verification_logic import (
    VerifiedClaim,
    VerifyDecision,
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
    candidate = structured_boolean_candidate_label(answer)
    if not candidate:
        return _invalid_candidate_decision(mode, answer)
    assessment = candidate_bound_boolean_claim_authority(
        prompt,
        candidate,
        evidence_bundle.items,
    )
    typed_boolean = project_boolean_assessment(assessment)
    semantic = semantic_boolean_verification(
        request,
        prompt,
        answer,
        evidence_bundle,
        typed_boolean,
        proposition_verifier,
    )
    domain = normalize_verification_domain(
        getattr(request, "verification_domain", None)
    )
    return finish_candidate_decision(
        request,
        retrieve_decision,
        evidence_bundle,
        answer=answer,
        mode=mode,
        candidate=candidate,
        prompt=prompt,
        domain=domain,
        typed_boolean=typed_boolean,
        semantic=semantic,
    )


def _invalid_candidate_decision(mode: str, answer: str) -> VerifyDecision:
    return VerifyDecision(
        mode=mode,
        status="unknown",
        reason="Structured Boolean candidate was invalid.",
        action="abstain",
        claims=[str(answer or "")],
        unknown_claims=[str(answer or "")],
    )


def semantic_boolean_verification(
    request: Any,
    prompt: str,
    answer: str,
    evidence_bundle: EvidenceBundle,
    deterministic: tuple[list[str], list[VerifiedClaim]],
    verifier: PropositionVerifier | None,
) -> tuple[list[str], list[VerifiedClaim]] | None:
    domain = normalize_verification_domain(
        getattr(request, "verification_domain", None)
    )
    qasper = domain == "qasper" or domain.startswith("qasper_")
    if verifier is None or (
        not qasper and any(result.status != "unknown" for result in deterministic[1])
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
