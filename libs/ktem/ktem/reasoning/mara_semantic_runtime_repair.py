from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.frozen_canonical_proposition_projection import (
    frozen_canonical_plan_projection_from_bundle,
    frozen_slot_support_by_ref,
)
from ktem.docqa.qasper_semantic_pack_contract import (
    QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY,
)
from ktem.docqa.question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
)
from ktem.docqa.recovery_progress import semantic_raw_evidence_digest
from ktem.docqa.semantic_evidence_set_validation import (
    semantic_evidence_set_runtime_validation_reason,
)

from .mara_semantic_proof_repair import semantic_proposal_binding_digest
from .mara_semantic_proposition_contract import (
    SemanticPropositionTransactionResult,
    insufficient_semantic_result,
    rejected_semantic_transaction,
)
from .mara_semantic_proposition_data_lineage import record_runtime_authority_rejection
from .mara_semantic_proposition_packing import SemanticPropositionEvidencePacking


def reject_runtime_contract_without_reverify(
    outcome: SemanticPropositionTransactionResult,
    *,
    request: Any,
    question: str,
    bundle: EvidenceBundle,
    packing: SemanticPropositionEvidencePacking,
    slots: list[dict[str, str]],
    release_mode: bool,
) -> SemanticPropositionTransactionResult:
    reason = _runtime_validation_reason(
        outcome.value,
        request=request,
        question=question,
        bundle=bundle,
        slots=slots,
        packing=packing,
        release_mode=release_mode,
    )
    if not reason:
        return outcome
    diagnostics = _runtime_rejection_diagnostics(
        outcome,
        reason,
        slots=slots,
        packing=packing,
        bundle=bundle,
    )
    return _runtime_rejected_outcome(outcome, diagnostics, question)


def _runtime_rejection_diagnostics(
    outcome: SemanticPropositionTransactionResult,
    reason: str,
    *,
    slots: list[dict[str, str]],
    packing: SemanticPropositionEvidencePacking,
    bundle: EvidenceBundle,
) -> dict[str, Any]:
    evidence_digest = _evidence_digest(bundle)
    slot_digest = _digest(slots)
    binding_digest = semantic_proposal_binding_digest(outcome.value)
    transition = {
        "from": "runtime_authority_contract",
        "to": "stop_without_reverify",
        "reason": reason,
        "outcome": "recovery_no_progress",
        "recovery_action": "stop_without_reverify",
        "stop_reason": "recovery_no_progress",
        "blocked_repair_kind": _runtime_repair_kind(reason),
        "evidence_digest_before": evidence_digest,
        "evidence_digest_after": evidence_digest,
        "evidence_digest_changed": False,
        "evidence_digest_applicable": bool(evidence_digest),
        "semantic_pack_digest_before": packing.semantic_pack_digest,
        "semantic_pack_digest_after": packing.semantic_pack_digest,
        "semantic_pack_digest_changed": False,
        "semantic_pack_digest_applicable": bool(packing.semantic_pack_digest),
        "slot_state_digest_before": slot_digest,
        "slot_state_digest_after": slot_digest,
        "slot_state_digest_changed": False,
        "slot_state_digest_applicable": bool(slot_digest),
        "proposition_binding_digest_before": binding_digest,
        "proposition_binding_digest_after": binding_digest,
        "proposition_binding_digest_changed": False,
        "proposition_binding_digest_applicable": bool(binding_digest),
    }
    diagnostics = deepcopy(outcome.diagnostics)
    diagnostics.setdefault("recovery_transitions", []).append(transition)
    diagnostics["recovery_no_progress_count"] = (
        int(diagnostics.get("recovery_no_progress_count") or 0) + 1
    )
    diagnostics["runtime_contract_rejection_count"] = (
        int(diagnostics.get("runtime_contract_rejection_count") or 0) + 1
    )
    if _has_verified_audit(outcome.value):
        diagnostics["audit_verified_but_runtime_rejected_count"] = (
            int(diagnostics.get("audit_verified_but_runtime_rejected_count") or 0) + 1
        )
    diagnostics["runtime_authority_rejection_reason"] = reason
    diagnostics.setdefault("rejected_transactions", []).append(
        _rejected_transaction(outcome.value or {}, reason, packing.semantic_pack_digest)
    )
    value = outcome.value or {}
    verifier = value.get("verifier")
    verifier = verifier if isinstance(verifier, Mapping) else {}
    record_runtime_authority_rejection(
        diagnostics,
        reason=reason,
        outcome_status=outcome.status,
        evidence_digest=evidence_digest,
        semantic_pack_digest=packing.semantic_pack_digest,
        slot_state_digest=slot_digest,
        proposition_binding_digest=binding_digest,
        canonical_plan_id=str(value.get("canonical_evidence_plan_id") or ""),
        canonical_plan_digest=str(value.get("canonical_plan_digest") or ""),
        canonical_projection_digest=str(
            verifier.get("canonical_projection_digest") or ""
        ),
    )
    return diagnostics


def _runtime_validation_reason(
    value: dict[str, Any] | None,
    *,
    request: Any,
    question: str,
    bundle: EvidenceBundle,
    slots: list[dict[str, str]],
    packing: SemanticPropositionEvidencePacking,
    release_mode: bool,
) -> str:
    if not value or value.get("verdict") == "insufficient_evidence":
        return ""
    projection, projection_reason = _runtime_plan_projection(
        value,
        question=question,
        bundle=bundle,
        slots=slots,
        packing=packing,
    )
    if projection_reason:
        return projection_reason
    return semantic_evidence_set_runtime_validation_reason(
        request,
        question,
        value,
        bundle.items,
        release_mode=release_mode,
        canonical_plan_projection=projection,
    )


def _runtime_plan_projection(
    value: Mapping[str, Any],
    *,
    question: str,
    bundle: EvidenceBundle,
    slots: list[dict[str, str]],
    packing: SemanticPropositionEvidencePacking,
) -> tuple[Any | None, str]:
    """Resolve runtime authority from the immutable plan, when one exists."""

    raw_pack = bundle.metadata.get(QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY)
    if not isinstance(raw_pack, Mapping):
        return None, ""
    plan_id = str(value.get("canonical_evidence_plan_id") or "").strip()
    if not plan_id:
        return None, "canonical_plan_projection_plan_missing"
    binding = raw_pack.get("proposition_binding")
    binding = binding if isinstance(binding, Mapping) else {}
    canonical = binding.get("canonical_evidence_plan")
    canonical = canonical if isinstance(canonical, Mapping) else {}
    selected = next(
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
    if selected is None:
        return None, "canonical_plan_projection_plan_missing"
    frozen_slots = raw_pack.get("slots")
    frozen_records = raw_pack.get("records")
    if not isinstance(frozen_slots, list) or not isinstance(frozen_records, list):
        return None, "canonical_plan_projection_pack_invalid"
    support_by_ref, support_reason = frozen_slot_support_by_ref(
        selected.get("span_refs") or (),
        frozen_slots,
    )
    if support_reason:
        return None, support_reason
    proposition = build_question_proposition(question)
    verifier = value.get("verifier")
    verifier = verifier if isinstance(verifier, Mapping) else {}
    expected_plan_digest = str(
        value.get("canonical_plan_digest")
        or verifier.get("canonical_plan_digest")
        or ""
    )
    if not expected_plan_digest:
        return None, "canonical_plan_projection_digest_mismatch"
    if list(getattr(packing, "records", ()) or ()) != frozen_records:
        return None, "canonical_plan_projection_frozen_records_invalid"
    return frozen_canonical_plan_projection_from_bundle(
        bundle,
        plan_id=plan_id,
        proposition=proposition,
        expected_slots=applicable_proposition_evidence_slots(proposition),
        expected_plan_digest=expected_plan_digest,
        slot_support_by_ref=support_by_ref,
    )


def _runtime_repair_kind(reason: str) -> str:
    normalized = reason.casefold()
    if "question_proposition" in normalized:
        return "proposition_repair"
    if any(value in normalized for value in ("quote", "offset", "span")):
        return "quote_rebind"
    return "proof_repair"


def _rejected_transaction(
    value: dict[str, Any],
    reason: str,
    semantic_pack_digest: str,
) -> dict[str, Any]:
    return rejected_semantic_transaction(
        value,
        reason=reason,
        semantic_pack_digest=semantic_pack_digest,
        semantic_proof_digest=_semantic_proof_digest(value),
    )


def _semantic_proof_digest(value: dict[str, Any] | None) -> str:
    if not value:
        return ""
    audit = value.get("entailment_audit")
    audit = audit if isinstance(audit, dict) else {}
    payload = {
        "verdict": str(value.get("verdict") or ""),
        "proof_mode": str(value.get("proof_mode") or ""),
        "premises": value.get("premises") or [],
        "typed_conclusion": value.get("typed_conclusion") or {},
        "audit_proposal_digest": str(audit.get("proposal_digest") or ""),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _evidence_digest(bundle: EvidenceBundle) -> str:
    return semantic_raw_evidence_digest(bundle)


def _digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _has_verified_audit(value: dict[str, Any] | None) -> bool:
    audit = (value or {}).get("entailment_audit")
    return bool(
        isinstance(audit, dict)
        and audit.get("status") == "verified"
        and (value or {}).get("typed_conclusion")
    )


def _runtime_rejected_outcome(
    outcome: SemanticPropositionTransactionResult,
    diagnostics: dict[str, Any],
    question: str,
) -> SemanticPropositionTransactionResult:
    source = outcome.value or {}
    source_verifier = source.get("verifier")
    source_verifier = source_verifier if isinstance(source_verifier, dict) else {}
    value = insufficient_semantic_result(
        str(source_verifier.get("model") or "runtime"),
        int(source_verifier.get("seed") or 0),
        question,
    )
    value["verifier"].update(
        {
            "release_mode": bool(source_verifier.get("release_mode")),
            "auditor_relationship": str(
                source_verifier.get("auditor_relationship") or ""
            ),
            "semantic_pack_digest": str(
                source_verifier.get("semantic_pack_digest") or ""
            ),
        }
    )
    resolution = source.get("question_proposition_resolution")
    if isinstance(resolution, dict):
        value["question_proposition_resolution"] = deepcopy(resolution)
    value["rejected_transaction"] = deepcopy(
        (diagnostics.get("rejected_transactions") or [{}])[-1]
    )
    return replace(
        outcome,
        value=value,
        status="runtime_rejected",
        reason=str(diagnostics.get("runtime_authority_rejection_reason") or ""),
        diagnostics=diagnostics,
    )
