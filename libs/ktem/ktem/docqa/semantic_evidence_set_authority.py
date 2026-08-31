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
from .canonical_serialization import canonical_projection_digest_trace
from .evidence_schema import EvidenceBundle
from .frozen_canonical_proposition_projection import (
    FrozenCanonicalPropositionEvidencePlan,
)
from .qasper_semantic_pack_contract import qasper_semantic_pack_continuity_reason
from .semantic_evidence_set_derivation import semantic_evidence_set_derivation
from .semantic_evidence_set_plan_projection import semantic_authority_plan_projection
from .semantic_evidence_set_authority_trace import (
    canonical_projection_trace as _canonical_projection_trace,
)
from .semantic_evidence_set_validation import (
    semantic_proposition_binding_fields,
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
    if not _canonical_pack_accepted(
        request,
        prompt,
        bundle,
        response,
        debug_trace,
    ):
        return None
    return _authority_from_response(
        request,
        prompt,
        answer,
        bundle,
        response,
        debug_trace,
    )


def _authority_from_response(
    request: Any,
    prompt: str,
    answer: str,
    bundle: EvidenceBundle,
    response: Mapping[str, Any],
    debug_trace: dict[str, Any] | None,
) -> BooleanClaimAuthority | None:
    canonical_plan_projection, projection_reason = semantic_authority_plan_projection(
        prompt,
        bundle,
        response,
        required=_qasper_semantic_pack_required(request, bundle),
    )
    if projection_reason:
        _append_debug_stage(
            debug_trace,
            "canonical_plan_projection",
            "rejected",
            projection_reason,
        )
        _record_trace(
            bundle,
            "rejected",
            projection_reason,
            debug_trace=debug_trace,
            **_rejected_transaction_fields(response),
        )
        return None
    if canonical_plan_projection is not None:
        _append_debug_stage(debug_trace, "canonical_plan_projection", "accepted", "")
    header, header_reason = validated_semantic_header(
        response,
        prompt,
        release_mode=_semantic_release_mode(request),
        canonical_plan_projection=canonical_plan_projection,
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
        _record_insufficient_authority(bundle, response, debug_trace)
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
        canonical_plan_projection=canonical_plan_projection,
    )


def _canonical_pack_accepted(
    request: Any,
    prompt: str,
    bundle: EvidenceBundle,
    response: Mapping[str, Any],
    debug_trace: dict[str, Any] | None,
) -> bool:
    if not _qasper_semantic_pack_required(request, bundle):
        return True
    reason = qasper_semantic_pack_continuity_reason(
        bundle,
        question=prompt,
        response=response,
    )
    if reason:
        _append_debug_stage(
            debug_trace,
            "canonical_semantic_pack",
            "rejected",
            reason,
        )
        _record_trace(
            bundle,
            "rejected",
            reason,
            debug_trace=debug_trace,
            **_rejected_transaction_fields(response),
        )
        return False
    _append_debug_stage(
        debug_trace,
        "canonical_semantic_pack",
        "accepted",
        "",
    )
    return True


def _record_insufficient_authority(
    bundle: EvidenceBundle,
    response: Mapping[str, Any],
    debug_trace: dict[str, Any] | None,
) -> None:
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
        verifier_input_candidate=str(response.get("verifier_input_candidate") or ""),
        candidate_verification_status=str(
            response.get("candidate_verification_status") or "unknown"
        ),
        candidate_verification_audit=dict(
            response.get("candidate_verification_audit") or {}
        ),
        audited_typed_conclusion=dict(response.get("audited_typed_conclusion") or {}),
        unknown_assessment=dict(response.get("unknown_assessment") or {}),
        **_canonical_pack_trace_fields(response),
        replacement_candidate_allowed=False,
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
    canonical_plan_projection: FrozenCanonicalPropositionEvidencePlan | None = None,
) -> BooleanClaimAuthority | None:
    premises, slot_support, scope_basis, premise_reason = validated_semantic_premises(
        request,
        prompt,
        verdict,
        response.get("premises"),
        bundle.items,
        proof_mode=str(response.get("proof_mode") or ""),
        canonical_plan_projection=canonical_plan_projection,
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
        question=prompt,
        verdict=verdict,
        premises=premises,
        premise_count=len(premises),
        scope_basis=scope_basis,
        slot_support=slot_support,
        canonical_plan_projection=canonical_plan_projection,
    )
    derivation = semantic_evidence_set_derivation(
        prompt,
        verdict,
        premises,
        attestation,
        slot_support=slot_support,
        canonical_plan_projection=canonical_plan_projection,
    )
    status = boolean_derivation_contract_status(
        derivation.as_dict(),
        [premise.as_dict() for premise in premises],
        question=prompt,
        canonical_polarity=verdict,
        canonical_plan_projection=canonical_plan_projection,
    )
    if status != "bound":
        _append_debug_stage(debug_trace, "derivation", "rejected", status)
        _record_trace(
            bundle,
            "rejected",
            status,
            debug_trace=debug_trace,
            **_rejected_transaction_fields(response, attestation=attestation),
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
    attestation = derivation.verifier_attestation or {}
    _record_trace(
        bundle,
        "verified",
        "semantic_evidence_set_bound",
        debug_trace=debug_trace,
        **_verified_authority_trace_fields(
            response,
            premises=premises,
            derivation=derivation,
            audit=audit,
            attestation=attestation,
        ),
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


def _verified_authority_trace_fields(
    response: Mapping[str, Any],
    *,
    premises: tuple[Any, ...],
    derivation: Any,
    audit: Mapping[str, Any],
    attestation: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "premise_count": len(premises),
        "derivation_id": derivation.derivation_id,
        "proof_mode": str(response.get("proof_mode") or ""),
        "question_proposition": dict(response.get("question_proposition") or {}),
        "typed_conclusion": dict(response.get("typed_conclusion") or {}),
        "conclusion_audit": dict(audit.get("conclusion_audit") or {}),
        "polarity_contradiction_check": dict(
            audit.get("polarity_contradiction_check") or {}
        ),
        "auditor_relationship": str(
            (response.get("verifier") or {}).get("auditor_relationship") or ""
        ),
        "semantic_pack_digest": str(
            (response.get("verifier") or {}).get("semantic_pack_digest") or ""
        ),
        **_canonical_pack_trace_fields(response),
        "evidence_relation": str(attestation.get("evidence_relation") or ""),
        "required_slot_ids": list(attestation.get("required_slot_ids") or []),
        "verified_slot_ids": list(attestation.get("required_slot_ids") or []),
        "required_proposition_slots": list(
            attestation.get("required_proposition_slots") or []
        ),
        "not_applicable_proposition_slots": list(
            attestation.get("not_applicable_proposition_slots") or []
        ),
        "proposition_slot_bindings": dict(
            attestation.get("proposition_slot_bindings") or {}
        ),
        "proposition_slot_evidence_refs": dict(
            attestation.get("proposition_slot_evidence_refs") or {}
        ),
        "proposition_slot_evidence": dict(
            attestation.get("proposition_slot_evidence") or {}
        ),
        "proposition_binding_evidence_set_refs": list(
            attestation.get("proposition_binding_evidence_set_refs") or []
        ),
        "proposition_evidence_set_digest": str(
            attestation.get("proposition_evidence_set_digest") or ""
        ),
        "verifier_input_candidate": str(response.get("verifier_input_candidate") or ""),
        "candidate_verification_status": str(
            response.get("candidate_verification_status") or "unknown"
        ),
        "replacement_candidate_allowed": False,
        "canonical_evidence_plan_id": str(
            attestation.get("canonical_evidence_plan_id") or ""
        ),
        "canonical_plan_digest": str(attestation.get("canonical_plan_digest") or ""),
        "canonical_projection_digest": str(
            attestation.get("canonical_projection_digest") or ""
        ),
        "canonical_projection_digest_trace": dict(
            attestation.get("canonical_projection_digest_trace") or {}
        ),
    }


def _enriched_attestation(
    attestation: dict[str, Any],
    response: Mapping[str, Any],
    *,
    question: str,
    verdict: str,
    premises: tuple[Any, ...],
    premise_count: int,
    scope_basis: str,
    slot_support: dict[str, tuple[str, ...]],
    canonical_plan_projection: FrozenCanonicalPropositionEvidencePlan | None = None,
) -> dict[str, Any]:
    verifier = response.get("verifier") or {}
    projection_fields = {}
    if canonical_plan_projection is not None:
        projection_trace = canonical_projection_digest_trace(canonical_plan_projection)
        projection_fields = {
            "canonical_evidence_plan_id": canonical_plan_projection.plan_id,
            "canonical_plan_digest": canonical_plan_projection.plan_digest,
            "canonical_projection_digest": projection_trace["validator_digest"],
            "canonical_projection_digest_trace": projection_trace,
        }
    return {
        **attestation,
        "premise_count": premise_count,
        "complete_proposition": True,
        "scope_basis": scope_basis,
        "proof_mode": (
            canonical_plan_projection.proof_mode
            if canonical_plan_projection is not None
            else str(response.get("proof_mode") or "")
        ),
        "question_proposition": dict(response.get("question_proposition") or {}),
        "typed_conclusion": dict(response.get("typed_conclusion") or {}),
        "semantic_pack_digest": str(verifier.get("semantic_pack_digest") or ""),
        "auditor_relationship": str(verifier.get("auditor_relationship") or ""),
        "required_slot_ids": sorted(
            {slot_id for values in slot_support.values() for slot_id in values}
        ),
        **semantic_proposition_binding_fields(
            question,
            verdict,
            premises,
            canonical_plan_projection=canonical_plan_projection,
        ),
        **projection_fields,
    }


def _rejected_transaction_fields(
    response: Mapping[str, Any],
    *,
    attestation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    audit = response.get("entailment_audit")
    audit = audit if isinstance(audit, Mapping) else {}
    typed_conclusion = dict(response.get("typed_conclusion") or {})
    conclusion_audit = dict(audit.get("conclusion_audit") or {})
    polarity_check = dict(audit.get("polarity_contradiction_check") or {})
    fields = {
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
        "candidate_verification_audit": dict(
            response.get("candidate_verification_audit") or {}
        ),
        "unknown_assessment": dict(response.get("unknown_assessment") or {}),
        **_canonical_pack_trace_fields(response),
    }
    projection_trace = _canonical_projection_trace(response, attestation=attestation)
    if projection_trace:
        fields["canonical_projection_digest_trace"] = projection_trace
        for key in ("canonical_projection_digest",):
            if projection_trace.get("validator_digest"):
                fields[key] = projection_trace["validator_digest"]
    return fields


def _canonical_pack_trace_fields(response: Mapping[str, Any]) -> dict[str, Any]:
    verifier = response.get("verifier")
    verifier = verifier if isinstance(verifier, Mapping) else {}
    audit: Mapping[str, Any] = {}
    for key in ("entailment_audit", "candidate_verification_audit"):
        value = response.get(key)
        if isinstance(value, Mapping) and isinstance(
            value.get("semantic_pack_identity"), Mapping
        ):
            audit = value
            break
    if not audit:
        rejected = response.get("rejected_transaction")
        if isinstance(rejected, Mapping) and isinstance(
            rejected.get("semantic_pack_identity"), Mapping
        ):
            audit = {"semantic_pack_identity": rejected["semantic_pack_identity"]}
    return {
        "semantic_pack_digest": str(verifier.get("semantic_pack_digest") or ""),
        "canonical_span_universe_digest": str(
            verifier.get("canonical_span_universe_digest") or ""
        ),
        "candidate_transaction_id": str(verifier.get("candidate_transaction_id") or ""),
        "canonical_pack_continuity_status": str(
            verifier.get("canonical_pack_continuity_status") or ""
        ),
        "auditor_semantic_pack_identity": dict(
            audit.get("semantic_pack_identity") or {}
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


def _qasper_semantic_pack_required(request: Any, bundle: EvidenceBundle) -> bool:
    domain = str(getattr(request, "verification_domain", "") or "").strip().casefold()
    family = str(getattr(request, "dataset_family", "") or "").strip().casefold()
    if domain != "qasper" and family != "qasper":
        return False
    trace = bundle.metadata.get("qasper_candidate_generation")
    pack = bundle.metadata.get("qasper_canonical_semantic_pack")
    return bool(
        isinstance(pack, Mapping)
        or (
            isinstance(trace, Mapping)
            and trace.get("contract_id") == "qasper_typed_candidate_generation.v2"
        )
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
