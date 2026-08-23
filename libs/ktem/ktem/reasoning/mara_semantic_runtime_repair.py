from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.semantic_evidence_set_validation import (
    semantic_evidence_set_runtime_validation_reason,
)

from .mara_semantic_proof_repair import merge_proof_repair_debug
from .mara_semantic_proposition_contract import (
    SemanticPropositionTransactionResult,
    insufficient_semantic_result,
    rejected_semantic_transaction,
)
from .mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
    SemanticPropositionEvidencePacking,
)
from .mara_semantic_proposition_transaction import run_semantic_proposition_transaction


def repair_runtime_contract_rejection(
    outcome: SemanticPropositionTransactionResult,
    *,
    request: Any,
    question: str,
    bundle: EvidenceBundle,
    proposal_llm: Any,
    audit_llm: Any,
    prompt: str,
    packing: SemanticPropositionEvidencePacking,
    slots: list[dict[str, str]],
    proposal_model: str,
    audit_model: str,
    seed: int,
    release_mode: bool,
    capture_debug_trace: bool,
) -> SemanticPropositionTransactionResult:
    reason = _runtime_validation_reason(
        outcome.value,
        request=request,
        question=question,
        bundle=bundle,
        release_mode=release_mode,
    )
    if not reason:
        return outcome
    repair_kind = _runtime_repair_kind(reason)
    diagnostics, transition = _initial_repair_state(
        outcome,
        reason,
        repair_kind,
        packing.semantic_pack_digest,
    )
    repaired_prompt = _runtime_repair_prompt(prompt, reason, repair_kind)
    if repaired_prompt is None:
        transition["outcome"] = "repair_prompt_bound_exceeded"
        return _runtime_rejected_outcome(outcome, diagnostics, question)
    repaired = run_semantic_proposition_transaction(
        proposal_llm,
        audit_llm,
        repaired_prompt,
        question=question,
        packed=packing.records,
        slots=slots,
        proposal_model=proposal_model,
        audit_model=audit_model,
        seed=seed + 30,
        release_mode=release_mode,
        semantic_pack_digest=packing.semantic_pack_digest,
        capture_debug_trace=capture_debug_trace,
    )
    repaired_reason = _runtime_validation_reason(
        repaired.value,
        request=request,
        question=question,
        bundle=bundle,
        release_mode=release_mode,
    )
    diagnostics = _repair_diagnostics(outcome, repaired, diagnostics)
    return _finish_runtime_repair(
        outcome,
        repaired,
        diagnostics,
        transition,
        initial_reason=reason,
        repaired_reason=repaired_reason,
        semantic_pack_digest=packing.semantic_pack_digest,
        question=question,
    )


def _initial_repair_state(
    outcome: SemanticPropositionTransactionResult,
    reason: str,
    repair_kind: str,
    semantic_pack_digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    transition = {
        "from": "runtime_authority_contract",
        "to": repair_kind,
        "reason": reason,
        "outcome": "rebuild_required",
    }
    diagnostics = deepcopy(outcome.diagnostics)
    diagnostics.setdefault("recovery_transitions", []).append(transition)
    diagnostics["runtime_contract_rejection_count"] = (
        int(diagnostics.get("runtime_contract_rejection_count") or 0) + 1
    )
    if _has_verified_audit(outcome.value):
        diagnostics["audit_verified_but_runtime_rejected_count"] = (
            int(diagnostics.get("audit_verified_but_runtime_rejected_count") or 0) + 1
        )
    diagnostics["runtime_authority_rejection_reason"] = reason
    diagnostics.setdefault("rejected_transactions", []).append(
        _rejected_transaction(outcome.value or {}, reason, semantic_pack_digest)
    )
    count_key = f"{repair_kind}_count"
    diagnostics[count_key] = int(diagnostics.get(count_key) or 0) + 1
    return diagnostics, transition


def _repair_diagnostics(
    initial: SemanticPropositionTransactionResult,
    repaired: SemanticPropositionTransactionResult,
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    merged = _merged_repair_diagnostics(diagnostics, repaired.diagnostics)
    merged["proof_reaudit_count"] = (
        int(merged.get("proof_reaudit_count") or 0) + repaired.audit_call_count
    )
    merged["full_reaudit"] = repaired.audit_call_count > 0
    before_digest = _semantic_proof_digest(initial.value)
    after_digest = _semantic_proof_digest(repaired.value)
    merged.update(
        {
            "semantic_proof_digest_before": before_digest,
            "semantic_proof_digest_after": after_digest,
            "semantic_proof_digest_changed": bool(
                before_digest and after_digest and before_digest != after_digest
            ),
        }
    )
    return merged


def _finish_runtime_repair(
    initial: SemanticPropositionTransactionResult,
    repaired: SemanticPropositionTransactionResult,
    diagnostics: dict[str, Any],
    transition: dict[str, Any],
    *,
    initial_reason: str,
    repaired_reason: str,
    semantic_pack_digest: str,
    question: str,
) -> SemanticPropositionTransactionResult:
    if repaired.value is None:
        _set_runtime_transition_outcome(diagnostics, initial_reason, "repair_failed")
        transition["outcome"] = "repair_failed"
        return _accumulated_result(initial, repaired, diagnostics, transition)
    if repaired_reason:
        return _still_rejected_result(
            initial,
            repaired,
            diagnostics,
            transition,
            initial_reason=initial_reason,
            repaired_reason=repaired_reason,
            semantic_pack_digest=semantic_pack_digest,
            question=question,
        )
    transition["outcome"] = _repair_transition_outcome(repaired)
    _set_runtime_transition_outcome(
        diagnostics,
        initial_reason,
        str(transition["outcome"]),
    )
    return _accumulated_result(initial, repaired, diagnostics, transition)


def _still_rejected_result(
    initial: SemanticPropositionTransactionResult,
    repaired: SemanticPropositionTransactionResult,
    diagnostics: dict[str, Any],
    transition: dict[str, Any],
    *,
    initial_reason: str,
    repaired_reason: str,
    semantic_pack_digest: str,
    question: str,
) -> SemanticPropositionTransactionResult:
    transition["outcome"] = "rejected"
    _set_runtime_transition_outcome(diagnostics, initial_reason, "rejected")
    diagnostics["runtime_contract_rejection_count"] = (
        int(diagnostics.get("runtime_contract_rejection_count") or 0) + 1
    )
    if _has_verified_audit(repaired.value):
        diagnostics["audit_verified_but_runtime_rejected_count"] = (
            int(diagnostics.get("audit_verified_but_runtime_rejected_count") or 0) + 1
        )
    diagnostics["runtime_authority_rejection_reason"] = repaired_reason
    diagnostics.setdefault("rejected_transactions", []).append(
        _rejected_transaction(
            repaired.value or {},
            repaired_reason,
            semantic_pack_digest,
        )
    )
    accumulated = _accumulated_result(initial, repaired, diagnostics, transition)
    return _runtime_rejected_outcome(accumulated, diagnostics, question)


def _accumulated_result(
    initial: SemanticPropositionTransactionResult,
    repaired: SemanticPropositionTransactionResult,
    diagnostics: dict[str, Any],
    transition: dict[str, Any],
) -> SemanticPropositionTransactionResult:
    return replace(
        repaired,
        diagnostics=diagnostics,
        proposal_call_count=(
            initial.proposal_call_count + repaired.proposal_call_count
        ),
        audit_call_count=initial.audit_call_count + repaired.audit_call_count,
        debug_trace=merge_proof_repair_debug(
            initial.debug_trace,
            repaired.debug_trace,
            transition=transition,
            repaired_proposal=repaired.value,
            repair_kind="rebuilt",
        ),
    )


def _runtime_validation_reason(
    value: dict[str, Any] | None,
    *,
    request: Any,
    question: str,
    bundle: EvidenceBundle,
    release_mode: bool,
) -> str:
    if not value or value.get("verdict") == "insufficient_evidence":
        return ""
    return semantic_evidence_set_runtime_validation_reason(
        request,
        question,
        value,
        bundle.items,
        release_mode=release_mode,
    )


def _runtime_repair_kind(reason: str) -> str:
    normalized = reason.casefold()
    if "question_proposition" in normalized or "typed_conclusion" in normalized:
        return "proposition_repair"
    if any(value in normalized for value in ("quote", "offset", "span")):
        return "quote_rebind"
    return "proof_repair"


def _runtime_repair_prompt(prompt: str, reason: str, repair_kind: str) -> str | None:
    instruction = (
        "\n\nDETERMINISTIC CONTRACT REPAIR: the independently audited proof was "
        f"rejected by the local {repair_kind} contract ({reason}). Rebuild from "
        "the canonical span selectors and address that exact rejection. Do not "
        "repeat the rejected proof. Return insufficient_evidence if no complete "
        "contract-valid proof exists."
    )
    if len(prompt) + len(instruction) > SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS:
        return None
    return prompt + instruction


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


def _merged_repair_diagnostics(
    initial: dict[str, Any],
    repaired: dict[str, Any],
) -> dict[str, Any]:
    merged = {**deepcopy(initial), **deepcopy(repaired)}
    merged["recovery_transitions"] = [
        *deepcopy(initial.get("recovery_transitions") or []),
        *deepcopy(repaired.get("recovery_transitions") or []),
    ]
    merged["rejected_transactions"] = [
        *deepcopy(initial.get("rejected_transactions") or []),
        *deepcopy(repaired.get("rejected_transactions") or []),
    ]
    for key in (
        "audit_call_rejection_count",
        "audit_verified_but_runtime_rejected_count",
        "proposition_repair_count",
        "proof_repair_count",
        "quote_rebind_count",
        "runtime_contract_rejection_count",
    ):
        merged[key] = int(initial.get(key) or 0) + int(repaired.get(key) or 0)
    return merged


def _set_runtime_transition_outcome(
    diagnostics: dict[str, Any],
    reason: str,
    outcome: str,
) -> None:
    for transition in diagnostics.get("recovery_transitions") or []:
        if (
            isinstance(transition, dict)
            and transition.get("from") == "runtime_authority_contract"
            and transition.get("reason") == reason
        ):
            transition["outcome"] = outcome
            return


def _has_verified_audit(value: dict[str, Any] | None) -> bool:
    audit = (value or {}).get("entailment_audit")
    return bool(
        isinstance(audit, dict)
        and audit.get("status") == "verified"
        and (value or {}).get("typed_conclusion")
    )


def _repair_transition_outcome(
    result: SemanticPropositionTransactionResult,
) -> str:
    if result.status in {"audit_rejected", "runtime_rejected"}:
        return "rejected"
    if str((result.value or {}).get("verdict") or "") in {"yes", "no"}:
        return "verified"
    return "insufficient"


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
