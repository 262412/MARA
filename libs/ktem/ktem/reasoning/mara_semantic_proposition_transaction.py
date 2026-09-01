from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import replace
from typing import Any

from ktem.docqa.question_proposition import typed_conclusion
from ktem.docqa.semantic_premise_proof_validation import (
    semantic_entailment_premise_validation_reason,
)

from .mara_semantic_audit_attestation import attach_verified_entailment_audit
from .mara_semantic_audit_execution import execute_semantic_entailment_audit
from .mara_semantic_candidate_policy import (
    candidate_bound_insufficient_result,
    candidate_from_prompt,
)
from .mara_semantic_conclusion_binding import (
    conclusion_audit_binding_reason,
    record_verified_conclusion_audit,
)
from .mara_semantic_frozen_audit_projection import frozen_canonical_audit_result
from .mara_semantic_local_consistency import record_local_premise_consistency
from .mara_semantic_proof_repair import (
    prune_invalid_premises,
    requires_proof_repair,
    semantic_proposal_binding_digest,
)
from .mara_semantic_proposition_contract import (
    SemanticPropositionTransactionContext,
    SemanticPropositionTransactionResult,
)
from .mara_semantic_proposition_data_lineage import (
    record_audit_data_lineage,
    record_proposal_data_lineage,
    record_validated_plan_projection_lineage,
)
from .mara_semantic_proposition_stages import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
    ParsedSemanticStage,
    audit_diagnostics,
    invalid_response_reason,
    proposal_diagnostics,
    proposal_stage,
)
from .mara_semantic_proposition_transaction_audit import (
    audit_failure_result as _audit_failure_result,
)
from .mara_semantic_proposition_transaction_audit import (
    audit_rejection_result as _audit_rejection_result,
)
from .mara_semantic_proposition_transaction_repair import (
    finalize_repair_result,
    stop_without_reverify,
)
from .mara_semantic_recovery_state import changed_binding_reaudit_transition
from .mara_semantic_transaction_context import prepare_transaction
from .mara_semantic_transaction_context import (
    transaction_context as _transaction_context,
)
from .mara_semantic_transaction_support import (
    applicable_proposition_slots,
    bind_semantic_runtime_fields,
    canonical_plan_projection_digest,
    canonical_plan_projection_for_context,
    semantic_pack_identity,
    transaction_debug,
    transaction_result,
)

_TransactionContext = SemanticPropositionTransactionContext


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
    canonical_span_universe_digest: str = "",
    candidate_transaction_id: str = "",
    allowed_proposition_slot_bindings: Mapping[str, Collection[str]] | None = None,
    allowed_proposition_evidence_plans: Mapping[str, Mapping[str, Any]] | None = None,
    plan_construction_trace: dict[str, Any] | None = None,
    source_packing_observation: dict[str, Any] | None = None,
    capture_debug_trace: bool = False,
    transaction_id: str = "",
    attempt_namespace: str = "initial",
) -> SemanticPropositionTransactionResult:
    relationship, diagnostics, resolution, start_failure = prepare_transaction(
        proposal_llm,
        audit_llm,
        question=question,
        proposal_model=proposal_model,
        audit_model=audit_model,
        seed=seed,
        release_mode=release_mode,
        semantic_pack_digest=semantic_pack_digest,
    )
    if start_failure is not None:
        return start_failure
    assert resolution is not None
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
        canonical_span_universe_digest=canonical_span_universe_digest,
        candidate_transaction_id=candidate_transaction_id,
        plan_construction_trace=plan_construction_trace,
        source_packing_observation=source_packing_observation,
        allowed_proposition_evidence_plans=allowed_proposition_evidence_plans,
    )
    candidate = candidate_from_prompt(prompt)
    proposal = _transaction_proposal(
        proposal_llm,
        prompt,
        context=context,
        packed=packed,
        slots=slots,
        model=proposal_model,
        seed=seed,
        candidate=candidate,
        allowed_proposition_slot_bindings=allowed_proposition_slot_bindings,
        allowed_proposition_evidence_plans=allowed_proposition_evidence_plans,
    )
    return _complete_proposal(
        context,
        proposal,
        diagnostics,
        candidate=candidate,
        allowed_proposition_slot_bindings=allowed_proposition_slot_bindings,
        allowed_proposition_evidence_plans=allowed_proposition_evidence_plans,
    )


def _transaction_proposal(
    proposal_llm: Any,
    prompt: str,
    *,
    context: _TransactionContext,
    packed: list[dict[str, Any]],
    slots: list[dict[str, str]],
    model: str,
    seed: int,
    candidate: str,
    allowed_proposition_slot_bindings: Mapping[str, Collection[str]] | None,
    allowed_proposition_evidence_plans: Mapping[str, Mapping[str, Any]] | None,
) -> ParsedSemanticStage:
    return proposal_stage(
        proposal_llm,
        prompt,
        packed=packed,
        slots=slots,
        model=model,
        seed=seed,
        candidate=candidate,
        applicable_proposition_slots=applicable_proposition_slots(context.proposition),
        allowed_proposition_slot_bindings=allowed_proposition_slot_bindings,
        allowed_proposition_evidence_plans=allowed_proposition_evidence_plans,
    )


def _complete_proposal(
    context: _TransactionContext,
    proposal: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    *,
    candidate: str,
    allowed_proposition_slot_bindings: Mapping[str, Collection[str]] | None,
    allowed_proposition_evidence_plans: Mapping[str, Mapping[str, Any]] | None,
) -> SemanticPropositionTransactionResult:
    diagnostics.update(proposal_diagnostics(proposal))
    record_proposal_data_lineage(
        diagnostics,
        proposal,
        context=context,
        candidate=candidate,
        applicable_proposition_slots=applicable_proposition_slots(context.proposition),
        allowed_proposition_slot_bindings=allowed_proposition_slot_bindings,
        allowed_proposition_evidence_plans=allowed_proposition_evidence_plans,
    )
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
    context, early_result = _prepare_audit_context(context, proposal, diagnostics)
    if early_result is not None:
        return early_result
    bind_semantic_runtime_fields(value, context)
    conclusion = typed_conclusion(context.proposition, str(value.get("verdict") or ""))
    value["typed_conclusion"] = conclusion.as_dict()
    local_constraint, audit, audit_input = execute_semantic_entailment_audit(
        context, value, conclusion
    )
    if audit.call_count > 0:
        diagnostics["auditor_semantic_pack_identity"] = semantic_pack_identity(context)
    diagnostics["independent_semantic_constraint"] = local_constraint
    diagnostics.update(audit_diagnostics(audit, model=context.audit_model))
    record_audit_data_lineage(diagnostics, audit)
    audit, local_consistency = _resolve_audit_authority(
        context,
        audit,
        diagnostics,
        value.get("premises") or [],
        local_constraint,
    )
    result = _audit_result(
        context,
        proposal,
        audit,
        diagnostics,
        local_consistency=local_consistency,
        local_constraint=local_constraint,
        audit_input=audit_input,
    )
    if local_constraint.get("status") != "passed":
        return stop_without_reverify(
            context,
            proposal,
            diagnostics,
            result,
            reason=str(
                local_constraint.get("reason") or "local_semantic_relation_rejected"
            ),
            source="independent_semantic_constraint",
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
    if str(value.get("canonical_evidence_plan_id") or ""):
        return result
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


def _resolve_audit_authority(
    context: _TransactionContext,
    audit: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    premises: list[dict[str, Any]],
    local_constraint: dict[str, Any],
) -> tuple[ParsedSemanticStage, dict[str, Any]]:
    local_consistency = record_local_premise_consistency(
        diagnostics,
        premises,
        audit.value,
    )
    return (
        _project_internally_inconsistent_canonical_audit(
            context,
            audit,
            diagnostics,
            local_consistency=local_consistency,
            local_constraint=local_constraint,
        ),
        local_consistency,
    )


def _project_internally_inconsistent_canonical_audit(
    context: _TransactionContext,
    audit: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    *,
    local_consistency: dict[str, Any],
    local_constraint: dict[str, Any],
) -> ParsedSemanticStage:
    projection = context.canonical_plan_projection
    if (
        projection is None
        or audit.value is None
        or local_consistency.get("status") != "auditor_internal_inconsistency"
        or local_consistency.get("disagreement_scope") != "literal_fragment_only"
        or local_consistency.get("override_eligible") is not True
        or local_constraint.get("status") != "passed"
    ):
        return audit
    projected = frozen_canonical_audit_result(audit.value, projection)
    diagnostics.update(
        {
            "audit_model_observation_status": "auditor_internal_inconsistency",
            "audit_authority_source": "frozen_canonical_plan_projection",
            "audit_projection_scope": "literal_fragment_only",
            "auditor_override_blocked": True,
            "audit_model_observation": dict(audit.value),
        }
    )
    return replace(audit, value=projected)


def _prepare_audit_context(
    context: _TransactionContext,
    proposal: ParsedSemanticStage,
    diagnostics: dict[str, Any],
) -> tuple[_TransactionContext, SemanticPropositionTransactionResult | None]:
    projection, projection_reason = canonical_plan_projection_for_context(
        context,
        proposal.value or {},
    )
    if projection_reason:
        diagnostics.update(
            {
                "audit_status": "not_started",
                "audit_execution_status": "not_started",
                "audit_reason": projection_reason,
                "canonical_plan_projection_status": "rejected",
            }
        )
        return context, transaction_result(
            None,
            "failed",
            projection_reason,
            diagnostics,
            proposal_calls=proposal.call_count,
            debug_trace=transaction_debug(context, proposal, None),
        )
    if projection is None:
        return context, None
    context = replace(context, canonical_plan_projection=projection)
    record_validated_plan_projection_lineage(diagnostics, projection)
    diagnostics["canonical_plan_projection_status"] = "validated"
    diagnostics["canonical_plan_digest"] = projection.plan_digest
    diagnostics["canonical_projection_digest"] = canonical_plan_projection_digest(
        projection
    )
    return context, None


def _audit_result(
    context: _TransactionContext,
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    *,
    local_consistency: dict[str, Any],
    local_constraint: dict[str, Any],
    audit_input: dict[str, Any],
) -> SemanticPropositionTransactionResult:
    debug_trace = transaction_debug(context, proposal, audit, audit_input=audit_input)
    failure = _audit_failure_result(
        context,
        proposal,
        audit,
        diagnostics,
        debug_trace,
        local_consistency=local_consistency,
        local_constraint=local_constraint,
    )
    if failure is not None:
        return failure
    assert audit.value is not None
    value = proposal.value or {}
    premise_reason = semantic_entailment_premise_validation_reason(
        value.get("premises") or [],
        context.proposition,
        audit_result=audit.value,
        canonical_plan_projection=context.canonical_plan_projection,
    )
    if premise_reason:
        diagnostics["audit_reason"] = premise_reason
        return _audit_rejection_result(
            context,
            proposal,
            audit,
            diagnostics,
            debug_trace,
            "semantic_entailment_premise_validation_rejected",
        )
    attach_verified_entailment_audit(
        value,
        context,
        audit.value,
        local_constraint,
        canonical_plan_projection=context.canonical_plan_projection,
    )
    binding_reason = conclusion_audit_binding_reason(
        context.question,
        value,
        context.proposition,
        release_mode=context.release_mode,
        canonical_plan_projection=context.canonical_plan_projection,
    )
    if binding_reason:
        diagnostics["audit_reason"] = binding_reason
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
        applicable_proposition_slots=applicable_proposition_slots(context.proposition),
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
