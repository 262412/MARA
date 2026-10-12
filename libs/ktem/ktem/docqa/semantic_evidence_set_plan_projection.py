from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .evidence_schema import EvidenceBundle
from .frozen_canonical_proposition_projection import (
    FrozenCanonicalPropositionEvidencePlan,
    frozen_canonical_plan_projection_from_bundle,
    frozen_slot_support_by_ref,
)
from .question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
)


def semantic_authority_plan_projection(
    question: str,
    bundle: EvidenceBundle,
    response: Mapping[str, Any],
    *,
    required: bool,
) -> tuple[FrozenCanonicalPropositionEvidencePlan | None, str]:
    """Resolve final authority only from the immutable selected QASPER plan."""

    if not required or str(response.get("verdict") or "") not in {"yes", "no"}:
        return None, ""
    plan_id = str(response.get("canonical_evidence_plan_id") or "").strip()
    if not plan_id:
        return None, "canonical_plan_projection_plan_missing"
    raw_pack = bundle.metadata.get("qasper_canonical_semantic_pack")
    if not isinstance(raw_pack, Mapping):
        return None, "canonical_plan_projection_pack_invalid"
    plan = _selected_plan(raw_pack, plan_id)
    if plan is None:
        return None, "canonical_plan_projection_plan_missing"
    pack_slots = raw_pack.get("slots")
    if not isinstance(pack_slots, list):
        return None, "canonical_plan_projection_pack_invalid"
    support_by_ref, support_reason = frozen_slot_support_by_ref(
        plan.get("span_refs") or (),
        pack_slots,
    )
    if support_reason:
        return None, support_reason
    expected_digest = _response_plan_digest(response)
    if not expected_digest:
        return None, "canonical_plan_projection_digest_mismatch"
    proposition = build_question_proposition(question)
    return frozen_canonical_plan_projection_from_bundle(
        bundle,
        plan_id=plan_id,
        proposition=proposition,
        expected_slots=applicable_proposition_evidence_slots(proposition),
        expected_plan_digest=expected_digest,
        slot_support_by_ref=support_by_ref,
    )


def semantic_authority_plan_projection_from_decision(
    question: str,
    bundle: EvidenceBundle,
    decision: Any,
) -> tuple[FrozenCanonicalPropositionEvidencePlan | None, str]:
    """Resolve the selected frozen plan from one semantic verifier decision."""

    if not isinstance(bundle.metadata.get("qasper_canonical_semantic_pack"), Mapping):
        return None, ""
    selected_id = str(_decision_value(decision, "selected_derivation_id", "") or "")
    results = _decision_value(decision, "claim_results", ()) or ()
    semantic_result = next(
        (
            value
            for value in results
            if isinstance(value, Mapping)
            and str(value.get("authority_status") or "") == "semantic_evidence_set"
        ),
        None,
    )
    if semantic_result is None:
        return None, ""
    derivations = [
        value
        for value in semantic_result.get("authority_derivations") or ()
        if isinstance(value, Mapping)
        and str(value.get("derivation_id") or "") == selected_id
    ]
    if len(derivations) != 1:
        return None, "canonical_plan_projection_plan_missing"
    attestation = derivations[0].get("verifier_attestation")
    if not isinstance(attestation, Mapping):
        return None, "canonical_plan_projection_plan_missing"
    response = {
        "verdict": str(
            attestation.get("verdict")
            or _decision_value(decision, "canonical_answer_polarity", "")
            or ""
        ),
        "canonical_evidence_plan_id": str(
            attestation.get("canonical_evidence_plan_id") or ""
        ),
        "canonical_plan_digest": str(attestation.get("canonical_plan_digest") or ""),
    }
    return semantic_authority_plan_projection(
        question,
        bundle,
        response,
        required=True,
    )


def _decision_value(decision: Any, key: str, default: Any) -> Any:
    if isinstance(decision, Mapping):
        return decision.get(key, default)
    return getattr(decision, key, default)


def _selected_plan(
    raw_pack: Mapping[str, Any],
    plan_id: str,
) -> Mapping[str, Any] | None:
    binding = raw_pack.get("proposition_binding")
    canonical = (
        binding.get("canonical_evidence_plan") if isinstance(binding, Mapping) else None
    )
    if not isinstance(canonical, Mapping):
        return None
    return next(
        (
            candidate
            for candidate in (
                canonical.get("support_plan"),
                canonical.get("contradiction_plan"),
            )
            if isinstance(candidate, Mapping)
            and str(candidate.get("plan_id") or "") == plan_id
        ),
        None,
    )


def _response_plan_digest(response: Mapping[str, Any]) -> str:
    verifier = response.get("verifier")
    verifier = verifier if isinstance(verifier, Mapping) else {}
    return str(
        response.get("canonical_plan_digest")
        or verifier.get("canonical_plan_digest")
        or ""
    )
