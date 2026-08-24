from __future__ import annotations

from dataclasses import replace
from typing import Any

from ktem.docqa.question_proposition import (
    PROPOSITION_EVIDENCE_SLOTS,
    question_proposition_completeness_reason,
    typed_conclusion,
)
from ktem.docqa.semantic_entailment_audit import semantic_entailment_audit_attestation
from ktem.docqa.semantic_premise_proof_validation import (
    semantic_entailment_premise_validation_reason,
)

from .mara_semantic_candidate_policy import (
    candidate_bound_insufficient_result,
    candidate_bound_semantic_audit_prompt,
    candidate_from_prompt,
)
from .mara_semantic_conclusion_binding import (
    conclusion_audit_binding_reason,
    record_verified_conclusion_audit,
)
from .mara_semantic_entailment_audit import (
    SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
    semantic_entailment_rejection_reason,
)
from .mara_semantic_local_consistency import record_local_premise_consistency
from .mara_semantic_proof_repair import (
    prune_invalid_premises,
    requires_proof_repair,
    semantic_proposal_binding_digest,
)
from .mara_semantic_proposition_contract import (
    SemanticPropositionTransactionContext,
    SemanticPropositionTransactionResult,
    incomplete_proposition_result,
    insufficient_semantic_result,
    rejected_semantic_transaction,
    resolve_proposition_precondition,
)
from .mara_semantic_proposition_debug import semantic_auditor_relationship
from .mara_semantic_proposition_stages import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
    ParsedSemanticStage,
    audit_diagnostics,
    audit_stage,
    invalid_response_reason,
    proposal_diagnostics,
    proposal_stage,
)
from .mara_semantic_proposition_transaction_repair import (
    finalize_repair_result,
    stop_without_reverify,
)
from .mara_semantic_recovery_state import changed_binding_reaudit_transition
from .mara_semantic_transaction_support import (
    audit_prompt_failure,
    bind_semantic_runtime_fields,
    transaction_debug,
    transaction_result,
)

_TransactionContext = SemanticPropositionTransactionContext


def _transaction_diagnostics(
    relationship: str,
    semantic_pack_digest: str,
) -> dict[str, Any]:
    return {
        "audit_status": "not_started",
        "audit_reason": "",
        "auditor_relationship": relationship,
        "semantic_pack_digest": semantic_pack_digest,
        "recovery_transitions": [],
    }


def run_semantic_proposition_transaction(
    proposal_llm: Any,
    audit_llm: Any,
    prompt: str,
    *,
    question: str,
    packed: list[dict[str, Any]],
    slots: list[dict[str, str]],
    proposal_model: str,
    audit_model: str,
    seed: int,
    release_mode: bool = False,
    semantic_pack_digest: str = "",
    capture_debug_trace: bool = False,
    transaction_id: str = "",
    attempt_namespace: str = "initial",
) -> SemanticPropositionTransactionResult:
    relationship = semantic_auditor_relationship(
        proposal_llm,
        audit_llm,
        proposal_model=proposal_model,
        audit_model=audit_model,
    )
    diagnostics = _transaction_diagnostics(relationship, semantic_pack_digest)
    if release_mode and relationship == "same_instance":
        diagnostics["audit_reason"] = "release_conclusion_auditor_not_independent"
        return transaction_result(
            None,
            "failed",
            "release_conclusion_auditor_not_independent",
            diagnostics,
            proposal_calls=0,
        )
    resolution = resolve_proposition_precondition(question, diagnostics)
    if question_proposition_completeness_reason(resolution.proposition):
        return incomplete_proposition_result(
            resolution,
            diagnostics,
            proposal_model=proposal_model,
            seed=seed,
            question=question,
            release_mode=release_mode,
            relationship=relationship,
            semantic_pack_digest=semantic_pack_digest,
        )
    context = _transaction_context(
        proposal_llm=proposal_llm,
        audit_llm=audit_llm,
        prompt=prompt,
        question=question,
        packed=packed,
        slots=slots,
        resolution=resolution,
        proposal_model=proposal_model,
        audit_model=audit_model,
        seed=seed,
        release_mode=release_mode,
        semantic_pack_digest=semantic_pack_digest,
        capture_debug_trace=capture_debug_trace,
        relationship=relationship,
        transaction_id=transaction_id,
        attempt_namespace=attempt_namespace,
    )
    candidate = candidate_from_prompt(prompt)
    proposal = proposal_stage(
        proposal_llm,
        prompt,
        packed=packed,
        slots=slots,
        model=proposal_model,
        seed=seed,
        candidate=candidate,
        applicable_proposition_slots=_applicable_proposition_slots(context.proposition),
    )
    return _complete_proposal(context, proposal, diagnostics, candidate=candidate)


def _applicable_proposition_slots(proposition: Any) -> tuple[str, ...]:
    return tuple(
        slot
        for slot in PROPOSITION_EVIDENCE_SLOTS
        if not (slot == "quantifier" and proposition.quantifier == "none")
    )


def _transaction_context(
    *,
    proposal_llm: Any,
    audit_llm: Any,
    prompt: str,
    question: str,
    packed: list[dict[str, Any]],
    slots: list[dict[str, str]],
    resolution: Any,
    proposal_model: str,
    audit_model: str,
    seed: int,
    release_mode: bool,
    semantic_pack_digest: str,
    capture_debug_trace: bool,
    relationship: str,
    transaction_id: str,
    attempt_namespace: str,
) -> _TransactionContext:
    return _TransactionContext(
        proposal_llm=proposal_llm,
        audit_llm=audit_llm,
        proposal_prompt=prompt,
        question=question,
        packed=packed,
        slots=slots,
        proposition=resolution.proposition,
        proposition_resolution=resolution.as_dict(),
        proposal_model=proposal_model,
        audit_model=audit_model,
        seed=seed,
        release_mode=release_mode,
        semantic_pack_digest=semantic_pack_digest,
        capture_debug_trace=capture_debug_trace,
        auditor_relationship=relationship,
        transaction_id=transaction_id,
        attempt_namespace=attempt_namespace,
    )


def _complete_proposal(
    context: _TransactionContext,
    proposal: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    *,
    candidate: str,
) -> SemanticPropositionTransactionResult:
    diagnostics.update(proposal_diagnostics(proposal))
    debug_trace = transaction_debug(context, proposal, None)
    if proposal.provider_failure_reason:
        return transaction_result(
            None,
            "failed",
            proposal.provider_failure_reason,
            diagnostics,
            proposal_calls=proposal.call_count,
            debug_trace=debug_trace,
        )
    if proposal.value is None:
        reason = invalid_response_reason(
            proposal.response,
            max_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
            invalid_reason="invalid_model_json",
        )
        return transaction_result(
            None,
            "failed",
            reason,
            diagnostics,
            proposal_calls=proposal.call_count,
            debug_trace=debug_trace,
        )
    if proposal.value["verdict"] == "insufficient_evidence":
        return candidate_bound_insufficient_result(
            context, proposal, diagnostics, candidate=candidate
        )
    return _audit_transaction(context, proposal, diagnostics)


def _audit_transaction(
    context: _TransactionContext,
    proposal: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    *,
    allow_proof_repair: bool = True,
) -> SemanticPropositionTransactionResult:
    value = proposal.value or {}
    bind_semantic_runtime_fields(value, context)
    conclusion = typed_conclusion(context.proposition, str(value.get("verdict") or ""))
    value["typed_conclusion"] = conclusion.as_dict()
    try:
        prompt = candidate_bound_semantic_audit_prompt(context, conclusion, value)
    except ValueError:
        return audit_prompt_failure(context, proposal, diagnostics)
    audit = audit_stage(
        context.audit_llm,
        prompt,
        len(value.get("premises") or []),
        seed=context.seed + 1,
        premise_slot_expectations={
            f"P{index}": tuple(
                str(slot) for slot in premise.get("binds_proposition_slots") or []
            )
            for index, premise in enumerate(value.get("premises") or [], start=1)
            if isinstance(premise, dict)
        },
        premise_slot_evidence={
            f"P{index}": {
                str(slot): str(premise.get("quote") or "")
                for slot in premise.get("binds_proposition_slots") or []
            }
            for index, premise in enumerate(value.get("premises") or [], start=1)
            if isinstance(premise, dict)
        },
    )
    diagnostics.update(audit_diagnostics(audit, model=context.audit_model))
    local_consistency = record_local_premise_consistency(
        diagnostics,
        value.get("premises") or [],
        audit.value,
    )
    result = _audit_result(
        context,
        proposal,
        audit,
        diagnostics,
        local_consistency=local_consistency,
    )
    if (
        allow_proof_repair
        and diagnostics.get("audit_reason") == "polarity_contradiction_detected"
    ):
        return stop_without_reverify(
            context,
            proposal,
            diagnostics,
            result,
            reason="polarity_contradiction_detected",
            source="runtime_contract",
        )
    repair_reason = str(diagnostics.get("audit_reason") or "")
    if not allow_proof_repair or not requires_proof_repair(
        audit,
        reason=repair_reason,
    ):
        return result
    return _repair_transaction(
        context,
        proposal,
        audit,
        diagnostics,
        result,
        reason=repair_reason,
    )


def _audit_result(
    context: _TransactionContext,
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    *,
    local_consistency: dict[str, Any],
) -> SemanticPropositionTransactionResult:
    debug_trace = transaction_debug(context, proposal, audit)
    failure = _audit_failure_result(
        context,
        proposal,
        audit,
        diagnostics,
        debug_trace,
        local_consistency=local_consistency,
    )
    if failure is not None:
        return failure
    assert audit.value is not None
    value = proposal.value or {}
    premise_reason = semantic_entailment_premise_validation_reason(
        value.get("premises") or [],
        context.proposition,
        audit_result=audit.value,
    )
    if premise_reason:
        diagnostics.update({"audit_status": "rejected", "audit_reason": premise_reason})
        return _audit_rejection_result(
            context,
            proposal,
            audit,
            diagnostics,
            debug_trace,
            "semantic_entailment_premise_validation_rejected",
        )
    value["entailment_audit"] = semantic_entailment_audit_attestation(
        context.question,
        value["verdict"],
        value["premises"],
        model=context.audit_model,
        seed=context.seed + 1,
        proof_mode=str(value.get("proof_mode") or ""),
        proposition=context.proposition,
        conclusion=typed_conclusion(context.proposition, str(value["verdict"])),
        auditor_relationship=context.auditor_relationship,
        audit_result=audit.value,
    )
    binding_reason = conclusion_audit_binding_reason(
        context.question,
        value,
        context.proposition,
        release_mode=context.release_mode,
    )
    if binding_reason:
        diagnostics.update({"audit_status": "rejected", "audit_reason": binding_reason})
        return _audit_rejection_result(
            context,
            proposal,
            audit,
            diagnostics,
            debug_trace,
            "semantic_entailment_audit_binding_rejected",
        )
    record_verified_conclusion_audit(diagnostics, value)
    return transaction_result(
        value,
        "parsed",
        "strict_schema_and_entailment_audit",
        diagnostics,
        proposal_calls=proposal.call_count,
        audit_calls=audit.call_count,
        debug_trace=debug_trace,
    )


def _audit_failure_result(
    context: _TransactionContext,
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    debug_trace: dict[str, Any] | None,
    *,
    local_consistency: dict[str, Any],
) -> SemanticPropositionTransactionResult | None:
    if audit.provider_failure_reason:
        return transaction_result(
            None,
            "failed",
            audit.provider_failure_reason,
            diagnostics,
            proposal_calls=proposal.call_count,
            audit_calls=audit.call_count,
            debug_trace=debug_trace,
        )
    if audit.value is None:
        reason = invalid_response_reason(
            audit.response,
            max_tokens=SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
            invalid_reason="invalid_entailment_audit_json",
        )
        diagnostics["audit_reason"] = reason
        return transaction_result(
            None,
            "failed",
            reason,
            diagnostics,
            proposal_calls=proposal.call_count,
            audit_calls=audit.call_count,
            debug_trace=debug_trace,
        )
    rejection_reason = (
        "auditor_internal_inconsistency"
        if local_consistency.get("status") == "auditor_internal_inconsistency"
        else semantic_entailment_rejection_reason(audit.value)
    )
    if not rejection_reason:
        return None
    diagnostics["audit_call_rejection_count"] = (
        int(diagnostics.get("audit_call_rejection_count") or 0) + 1
    )
    diagnostics.update({"audit_status": "rejected", "audit_reason": rejection_reason})
    return _audit_rejection_result(
        context,
        proposal,
        audit,
        diagnostics,
        debug_trace,
        "semantic_entailment_audit_rejected",
    )


def _audit_rejection_result(
    context: _TransactionContext,
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    debug_trace: dict[str, Any] | None,
    reason: str,
) -> SemanticPropositionTransactionResult:
    diagnostics.setdefault("rejected_transactions", []).append(
        rejected_semantic_transaction(
            proposal.value or {},
            reason=str(diagnostics.get("audit_reason") or reason),
            semantic_pack_digest=str(diagnostics.get("semantic_pack_digest") or ""),
            raw_audit_result=audit.value or {},
            local_premise_consistency=dict(
                diagnostics.get("local_premise_consistency") or {}
            ),
        )
    )
    value = insufficient_semantic_result(
        context.proposal_model, context.seed, context.question
    )
    bind_semantic_runtime_fields(value, context)
    value["rejected_transaction"] = dict(
        (diagnostics.get("rejected_transactions") or [{}])[-1]
    )
    return transaction_result(
        value,
        "audit_rejected",
        reason,
        diagnostics,
        proposal_calls=proposal.call_count,
        audit_calls=audit.call_count,
        debug_trace=debug_trace,
    )


def _repair_transaction(
    context: _TransactionContext,
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    initial_result: SemanticPropositionTransactionResult,
    *,
    reason: str,
) -> SemanticPropositionTransactionResult:
    repaired = prune_invalid_premises(
        proposal,
        audit,
        context.slots,
        reason=reason,
        applicable_proposition_slots=_applicable_proposition_slots(context.proposition),
    )
    if repaired is None:
        return stop_without_reverify(
            context,
            proposal,
            diagnostics,
            initial_result,
            reason=reason,
            source="semantic_audit",
        )
    before_digest = semantic_proposal_binding_digest(proposal.value)
    after_digest = semantic_proposal_binding_digest(repaired.value)
    if before_digest == after_digest:
        return stop_without_reverify(
            context,
            proposal,
            diagnostics,
            initial_result,
            reason=reason,
            source="semantic_audit",
        )
    transition = changed_binding_reaudit_transition(
        context.packed,
        context.slots,
        reason=reason,
        binding_before=before_digest,
        binding_after=after_digest,
    )
    diagnostics.setdefault("recovery_transitions", []).append(transition)
    diagnostics["proof_repair_count"] = (
        int(diagnostics.get("proof_repair_count") or 0) + 1
    )
    repaired_result = _audit_transaction(
        replace(
            context,
            seed=context.seed + 10,
            attempt_namespace="proof_reaudit",
        ),
        repaired,
        diagnostics,
        allow_proof_repair=False,
    )
    diagnostics["proof_reaudit_count"] = (
        int(diagnostics.get("proof_reaudit_count") or 0) + 1
    )
    diagnostics["full_reaudit"] = True
    if repaired_result.status == "parsed":
        diagnostics.update(
            {
                "audit_status": "verified_after_proof_repair",
                "audit_reason": reason,
            }
        )
    return finalize_repair_result(
        proposal,
        audit,
        repaired,
        initial_result,
        repaired_result,
        transition,
        "pruned",
    )
