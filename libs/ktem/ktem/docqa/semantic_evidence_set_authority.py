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
from .boolean_claim_verification import canonical_boolean_answer_polarity
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
        _record_trace(bundle, "rejected", header_reason, debug_trace=debug_trace)
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
        _record_trace(bundle, "rejected", premise_reason, debug_trace=debug_trace)
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
        _record_trace(bundle, "rejected", status, debug_trace=debug_trace)
        return None
    _append_debug_stage(debug_trace, "derivation", "bound", "")
    _record_trace(
        bundle,
        "verified",
        "semantic_evidence_set_bound",
        debug_trace=debug_trace,
        premise_count=len(premises),
        derivation_id=derivation.derivation_id,
        proof_mode=str(response.get("proof_mode") or ""),
        typed_conclusion=dict(response.get("typed_conclusion") or {}),
        semantic_pack_digest=str(
            (response.get("verifier") or {}).get("semantic_pack_digest") or ""
        ),
    )
    return supported_boolean_claim(
        prompt,
        canonical_boolean_answer_polarity(answer),
        verdict,
        premises,
        reason="semantic_evidence_set_proposition",
        authority_derivations=(derivation,),
        selected_derivation_id=derivation.derivation_id,
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
