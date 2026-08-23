from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any, TypeAlias

from .boolean_authority_derivation import boolean_derivation_contract_status
from .boolean_authority_schema import (
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
    BooleanClaimAuthority,
    supported_boolean_claim,
)
from .boolean_candidate_authority import structured_boolean_candidate_label
from .evidence_schema import EvidenceBundle
from .semantic_evidence_set_derivation import semantic_evidence_set_derivation
from .semantic_evidence_set_validation import (
    validated_semantic_header,
    validated_semantic_premises,
)
from .semantic_proposition_authority_debug import (
    append_semantic_authority_debug_stage as _append_debug_stage,
)
from .semantic_proposition_authority_debug import (
    begin_semantic_authority_debug_attempt as _begin_debug_attempt,
)

LOGGER = logging.getLogger(__name__)

PropositionVerifier: TypeAlias = Callable[
    [Any, str, str, EvidenceBundle],
    Mapping[str, Any] | None,
]


def semantic_evidence_set_claim_authority(
    request: Any,
    prompt: str,
    answer: str,
    bundle: EvidenceBundle,
    verifier: PropositionVerifier,
) -> BooleanClaimAuthority | None:
    """Validate a verifier-selected exact premise set as one typed proposition."""

    response = _call_verifier(verifier, request, prompt, answer, bundle)
    debug_trace = _begin_debug_attempt(bundle)
    if response is None:
        _append_debug_stage(
            debug_trace, "verifier", "failed", "semantic_verifier_failed"
        )
        _record_trace(
            bundle,
            "failed",
            "semantic_verifier_failed",
            debug_trace=debug_trace,
        )
        return None
    verifier_trace = bundle.metadata.get("semantic_proposition_verifier") or {}
    _append_debug_stage(
        debug_trace,
        "verifier",
        str(verifier_trace.get("status") or "returned"),
        str(verifier_trace.get("reason") or ""),
    )
    header, header_reason = validated_semantic_header(
        response,
        prompt,
        release_mode=_semantic_release_mode(request),
    )
    if header is None:
        _append_debug_stage(debug_trace, "header", "rejected", header_reason)
        _record_trace(
            bundle,
            "rejected",
            header_reason,
            debug_trace=debug_trace,
            **_rejected_transaction_fields(response),
        )
        return None
    _append_debug_stage(debug_trace, "header", "accepted", "")
    verdict, attestation = header
    if verdict == "insufficient_evidence":
        _append_debug_stage(
            debug_trace,
            "premises",
            "not_required",
            "semantic_evidence_set_insufficient",
        )
        _record_trace(
            bundle,
            "insufficient",
            "semantic_evidence_set_insufficient",
            debug_trace=debug_trace,
            verifier_input_candidate=str(
                response.get("verifier_input_candidate") or ""
            ),
            candidate_verification_status=str(
                response.get("candidate_verification_status") or "unknown"
            ),
            replacement_candidate_allowed=False,
        )
        return None
    return _authority_from_verified_response(
        request,
        prompt,
        answer,
        bundle,
        response,
        verdict,
        attestation,
        debug_trace,
    )


def _authority_from_verified_response(
    request: Any,
    prompt: str,
    answer: str,
    bundle: EvidenceBundle,
    response: Mapping[str, Any],
    verdict: str,
    attestation: dict[str, Any],
    debug_trace: dict[str, Any] | None,
) -> BooleanClaimAuthority | None:
    premises, slot_support, scope_basis, premise_reason = validated_semantic_premises(
        request,
        prompt,
        verdict,
        response.get("premises"),
        bundle.items,
        proof_mode=str(response.get("proof_mode") or ""),
    )
    if premises is None:
        _append_debug_stage(debug_trace, "premises", "rejected", premise_reason)
        _record_trace(
            bundle,
            "rejected",
            premise_reason,
            debug_trace=debug_trace,
            **_rejected_transaction_fields(response),
        )
        return None
    _append_debug_stage(debug_trace, "premises", "accepted", "")
    attestation = _enriched_attestation(
        attestation,
        response,
        premise_count=len(premises),
        scope_basis=scope_basis,
        slot_support=slot_support,
    )
    derivation = semantic_evidence_set_derivation(
        prompt,
        verdict,
        premises,
        attestation,
        slot_support=slot_support,
    )
    status = boolean_derivation_contract_status(
        derivation.as_dict(),
        [premise.as_dict() for premise in premises],
        question=prompt,
        canonical_polarity=verdict,
    )
    if status != "bound":
        _append_debug_stage(debug_trace, "derivation", "rejected", status)
        _record_trace(
            bundle,
            "rejected",
            status,
            debug_trace=debug_trace,
            **_rejected_transaction_fields(response),
        )
        return None
    return _commit_verified_authority(
        prompt,
        answer,
        bundle,
        response,
        verdict,
        premises,
        derivation,
        debug_trace,
    )


def _commit_verified_authority(
    prompt: str,
    answer: str,
    bundle: EvidenceBundle,
    response: Mapping[str, Any],
    verdict: str,
    premises: tuple[Any, ...],
    derivation: Any,
    debug_trace: dict[str, Any] | None,
) -> BooleanClaimAuthority:
    _append_debug_stage(debug_trace, "derivation", "bound", "")
    audit = response.get("entailment_audit")
    audit = audit if isinstance(audit, Mapping) else {}
    _record_trace(
        bundle,
        "verified",
        "semantic_evidence_set_bound",
        debug_trace=debug_trace,
        premise_count=len(premises),
        derivation_id=derivation.derivation_id,
        proof_mode=str(response.get("proof_mode") or ""),
        question_proposition=dict(response.get("question_proposition") or {}),
        typed_conclusion=dict(response.get("typed_conclusion") or {}),
        conclusion_audit=dict(audit.get("conclusion_audit") or {}),
        polarity_contradiction_check=dict(
            audit.get("polarity_contradiction_check") or {}
        ),
        auditor_relationship=str(
            (response.get("verifier") or {}).get("auditor_relationship") or ""
        ),
        semantic_pack_digest=str(
            (response.get("verifier") or {}).get("semantic_pack_digest") or ""
        ),
        verifier_input_candidate=str(response.get("verifier_input_candidate") or ""),
        candidate_verification_status=str(
            response.get("candidate_verification_status") or "unknown"
        ),
        replacement_candidate_allowed=False,
    )
    candidate = structured_boolean_candidate_label(answer)
    assessment = supported_boolean_claim(
        prompt,
        candidate if candidate in {"yes", "no"} else "",
        verdict,
        premises,
        reason="semantic_evidence_set_proposition",
        authority_derivations=(derivation,),
        selected_derivation_id=derivation.derivation_id,
    )
    if str(response.get("candidate_verification_status") or "") != "contradicted":
        return assessment
    return BooleanClaimAuthority(
        claim=f"{candidate}: {prompt}",
        status="contradicted",
        input_answer_polarity=candidate,
        canonical_answer_polarity="",
        semantic_correction_applied=False,
        contradicting=assessment.supporting,
        reason="semantic_candidate_contradicted",
        authority_derivations=assessment.authority_derivations,
        selected_derivation_id=assessment.selected_derivation_id,
    )


def _enriched_attestation(
    attestation: dict[str, Any],
    response: Mapping[str, Any],
    *,
    premise_count: int,
    scope_basis: str,
    slot_support: dict[str, tuple[str, ...]],
) -> dict[str, Any]:
    verifier = response.get("verifier") or {}
    return {
        **attestation,
        "premise_count": premise_count,
        "complete_proposition": True,
        "scope_basis": scope_basis,
        "proof_mode": str(response.get("proof_mode") or ""),
        "question_proposition": dict(response.get("question_proposition") or {}),
        "typed_conclusion": dict(response.get("typed_conclusion") or {}),
        "semantic_pack_digest": str(verifier.get("semantic_pack_digest") or ""),
        "auditor_relationship": str(verifier.get("auditor_relationship") or ""),
        "required_slot_ids": sorted(
            {slot_id for values in slot_support.values() for slot_id in values}
        ),
    }


def _rejected_transaction_fields(response: Mapping[str, Any]) -> dict[str, Any]:
    audit = response.get("entailment_audit")
    audit = audit if isinstance(audit, Mapping) else {}
    typed_conclusion = dict(response.get("typed_conclusion") or {})
    conclusion_audit = dict(audit.get("conclusion_audit") or {})
    polarity_check = dict(audit.get("polarity_contradiction_check") or {})
    return {
        "proof_mode": str(response.get("proof_mode") or ""),
        "typed_conclusion": typed_conclusion,
        "conclusion_audit": conclusion_audit,
        "polarity_contradiction_check": polarity_check,
        "audited_typed_conclusion": typed_conclusion,
        "audited_conclusion_audit": conclusion_audit,
        "audit_verified_but_runtime_rejected": bool(
            audit.get("status") == "verified" and typed_conclusion
        ),
        "semantic_pack_digest": str(
            (response.get("verifier") or {}).get("semantic_pack_digest") or ""
        ),
    }


def _call_verifier(
    verifier: PropositionVerifier,
    request: Any,
    prompt: str,
    answer: str,
    bundle: EvidenceBundle,
) -> Mapping[str, Any] | None:
    try:
        response = verifier(request, prompt, answer, bundle)
    except Exception:
        LOGGER.exception("Semantic proposition verifier failed")
        return None
    return response if isinstance(response, Mapping) else None


def _semantic_release_mode(request: Any) -> bool:
    return bool(
        str(getattr(request, "origin", "") or "").strip().casefold() == "benchmark"
        and str(getattr(request, "verification_domain", "") or "").strip().casefold()
        == "qasper"
        and str(getattr(request, "verification_mode", "") or "").strip().casefold()
        == "strict"
    )


def _record_trace(
    bundle: EvidenceBundle,
    status: str,
    reason: str,
    *,
    debug_trace: dict[str, Any] | None = None,
    **fields: Any,
) -> None:
    trace = {
        "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "status": status,
        "reason": reason,
        **fields,
    }
    if debug_trace is not None:
        trace["debug_trace"] = debug_trace
    bundle.metadata["semantic_proposition_authority"] = trace
