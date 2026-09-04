from __future__ import annotations

from dataclasses import replace
from typing import Any

from .boolean_authority_schema import BooleanClaimAuthority
from .boolean_verification_projection import project_boolean_assessment
from .evidence import EvidenceBundle
from .typed_proposition_authority import resolve_typed_proposition_authority_transaction
from .verification_logic import (
    VerifiedClaim,
    VerifyDecision,
    _decision_for_claim_results,
)

CANDIDATE_VERIFICATION_CONTRACT = "candidate_proposition_verification.v2"


def candidate_claim_results(
    candidate: str,
    prompt: str,
    typed_boolean: tuple[list[str], list[VerifiedClaim]],
    semantic: tuple[list[str], list[VerifiedClaim]] | None,
    *,
    qasper: bool,
) -> tuple[list[str], list[VerifiedClaim]]:
    if qasper:
        return semantic or project_boolean_assessment(
            BooleanClaimAuthority(
                claim=f"{candidate}: {prompt}",
                status="unknown",
                input_answer_polarity=candidate,
                canonical_answer_polarity="",
                semantic_correction_applied=False,
                reason="candidate_verifier_authority_missing",
            )
        )
    return semantic or typed_boolean


def finish_candidate_decision(
    request: Any,
    retrieve_decision: Any,
    evidence_bundle: EvidenceBundle,
    *,
    answer: str,
    mode: str,
    candidate: str,
    prompt: str,
    domain: str,
    typed_boolean: tuple[list[str], list[VerifiedClaim]],
    semantic: tuple[list[str], list[VerifiedClaim]] | None,
) -> VerifyDecision | None:
    qasper = domain == "qasper" or domain.startswith("qasper_")
    claims, results = candidate_claim_results(
        candidate,
        prompt,
        typed_boolean,
        semantic,
        qasper=qasper,
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
    verifier_trace = evidence_bundle.metadata.get("semantic_proposition_verifier")
    verifier_trace = verifier_trace if isinstance(verifier_trace, dict) else {}
    relation = str(verifier_trace.get("candidate_verification_status") or "unknown")
    decision = replace(
        decision,
        candidate_contract_id=CANDIDATE_VERIFICATION_CONTRACT,
        candidate_label=candidate,
        verifier_input_candidate=str(
            verifier_trace.get("candidate_label") or candidate
        ),
        verifier_candidate_status=relation,
        replacement_candidate_allowed=False,
    )
    if relation in {"contradicted", "unknown"}:
        decision = replace(decision, action="abstain")
    if candidate == "unanswerable" and _audited_unknown_candidate(
        verifier_trace,
        candidate=candidate,
        relation=relation,
    ):
        return replace(
            decision,
            status="supported",
            reason="Candidate-bound auditor verified the unknown evidence gap.",
            action="generate",
            unsupported_claims=[],
            unknown_claims=[],
            typed_authority={
                "contract_id": CANDIDATE_VERIFICATION_CONTRACT,
                "state": "verified_abstention",
                "candidate_label": candidate,
                "verifier_candidate_status": relation,
                "replacement_candidate_allowed": False,
            },
        )
    return _resolve_candidate_authority(
        request,
        decision,
        evidence_bundle,
        answer=answer,
        prompt=prompt,
        domain=domain,
        candidate=candidate,
        relation=relation,
        verifier_trace=verifier_trace,
        qasper=qasper,
    )


def _audited_unknown_candidate(
    verifier_trace: dict[str, Any],
    *,
    candidate: str,
    relation: str,
) -> bool:
    audit = verifier_trace.get("candidate_verification_audit")
    return bool(
        relation == "unknown"
        and isinstance(audit, dict)
        and audit.get("contract_id") == "candidate_verifier_audit.v2"
        and audit.get("status") == "passed"
        and audit.get("mode") == "candidate_bound_unknown_audit"
        and audit.get("audited_candidate") == candidate
        and audit.get("audited_verdict") == "insufficient_evidence"
        and audit.get("audited_judgment") == "unknown"
        and audit.get("replacement_candidate_allowed") is False
    )


def _resolve_candidate_authority(
    request: Any,
    decision: VerifyDecision,
    evidence_bundle: EvidenceBundle,
    *,
    answer: str,
    prompt: str,
    domain: str,
    candidate: str,
    relation: str,
    verifier_trace: dict[str, Any],
    qasper: bool,
) -> VerifyDecision | None:
    typed = resolve_typed_proposition_authority_transaction(
        request,
        decision,
        evidence_bundle,
        question=prompt,
        answer=answer,
        domain=domain,
    )
    if not qasper:
        return (
            typed
            if typed is not None and typed.status in {"supported", "verified_conflict"}
            else None
        )
    if typed is None or relation == "contradicted":
        return decision
    return replace(
        typed,
        candidate_contract_id=CANDIDATE_VERIFICATION_CONTRACT,
        candidate_label=candidate,
        verifier_input_candidate=str(
            verifier_trace.get("candidate_label") or candidate
        ),
        verifier_candidate_status=relation,
        replacement_candidate_allowed=False,
    )
