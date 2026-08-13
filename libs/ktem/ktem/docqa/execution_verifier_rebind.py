from __future__ import annotations

from typing import Any

from .evidence import EvidenceBundle, build_evidence_bundle

_DERIVED_VERIFICATION_KEYS = {
    "boolean_authority",
    "pending_verification_slot_ids",
    "pre_guardrail_answer",
    "pre_verification_answer",
    "verification_slot_states",
    "verified_claim_support_by_claim",
    "verified_claim_support_evidence",
    "verified_claim_support_spans",
    "verified_evidence",
    "verify_decision",
}


def rebind_existing_boolean_evidence(
    request: Any,
    route: str,
    bundle: EvidenceBundle,
) -> EvidenceBundle:
    """Rebuild Boolean slot bindings without issuing another retrieval call."""

    metadata = {
        key: value
        for key, value in bundle.metadata.items()
        if key not in _DERIVED_VERIFICATION_KEYS
    }
    metadata["evidence"] = list(bundle.items)
    metadata["verifier_rebind_attempt"] = 1
    rebound = build_evidence_bundle(route, request, metadata)
    rebound_metadata = dict(rebound.metadata)
    rebound_metadata["retrieval_rounds"] = int(
        bundle.metadata.get("retrieval_rounds") or 1
    )
    rebound_metadata["verifier_rebind_attempt"] = 1
    return EvidenceBundle(
        route=rebound.route,
        items=rebound.items,
        metadata=rebound_metadata,
    )
