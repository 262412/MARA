from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ktem.docqa.frozen_canonical_proposition_projection import (
    FrozenCanonicalPropositionEvidencePlan,
    frozen_canonical_plan_projection_checked,
    frozen_slot_support_by_ref,
)
from ktem.docqa.qasper_semantic_pack_contract import canonical_payload_digest
from ktem.docqa.question_proposition import (
    PROPOSITION_EVIDENCE_SLOTS,
    proposition_evidence_bindings,
)

from .mara_semantic_proposition_contract import (
    SemanticPropositionTransactionContext,
    SemanticPropositionTransactionResult,
)
from .mara_semantic_proposition_data_lineage import finalize_semantic_data_lineage
from .mara_semantic_proposition_debug import semantic_transaction_debug
from .mara_semantic_proposition_stages import ParsedSemanticStage


def pre_audit_transaction_failure(
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    debug_trace: dict[str, Any] | None,
) -> SemanticPropositionTransactionResult:
    reason = audit.failure_reason or "pre_audit_failed"
    diagnostics["audit_reason"] = reason
    return transaction_result(
        None,
        "failed",
        reason,
        diagnostics,
        proposal_calls=proposal.call_count,
        audit_calls=0,
        debug_trace=debug_trace,
    )


def applicable_proposition_slots(proposition: Any) -> tuple[str, ...]:
    return tuple(
        slot
        for slot in PROPOSITION_EVIDENCE_SLOTS
        if not (slot == "quantifier" and proposition.quantifier == "none")
    )


def bind_semantic_runtime_fields(
    value: dict[str, Any],
    context: SemanticPropositionTransactionContext,
) -> None:
    evidence_relation = str(value.get("evidence_relation") or "")
    projection = getattr(context, "canonical_plan_projection", None)
    if projection is not None:
        evidence_relation = projection.polarity_relation
        value["canonical_evidence_plan_id"] = projection.plan_id
        value["canonical_plan_digest"] = projection.plan_digest
        value["proof_mode"] = projection.proof_mode
        value["evidence_relation"] = evidence_relation
        value["premises"] = deepcopy(list(projection.premises))
    else:
        canonical_bindings = proposition_evidence_bindings(context.proposition)
        for premise in value.get("premises") or []:
            if not isinstance(premise, dict):
                continue
            bound_slots = premise.get("binds_proposition_slots") or []
            premise["proposition_slot_bindings"] = {
                slot: canonical_bindings[slot]
                for slot in bound_slots
                if slot in canonical_bindings
            }
            premise["evidence_relation"] = evidence_relation
    bind_semantic_execution_identity(value, context)


def bind_semantic_execution_identity(
    value: dict[str, Any],
    context: SemanticPropositionTransactionContext,
) -> None:
    """Bind one transaction identity without promoting its semantic result."""

    value["question_proposition"] = context.proposition.as_dict()
    value["question_proposition_resolution"] = dict(context.proposition_resolution)
    projection = getattr(context, "canonical_plan_projection", None)
    value.setdefault("verifier", {}).update(
        {
            "release_mode": context.release_mode,
            "auditor_relationship": context.auditor_relationship,
            "semantic_pack_digest": context.semantic_pack_digest,
            "canonical_span_universe_digest": (context.canonical_span_universe_digest),
            "candidate_transaction_id": context.candidate_transaction_id,
            "canonical_pack_continuity_status": "preserved",
            **(
                {
                    "canonical_plan_digest": projection.plan_digest,
                    "canonical_projection_digest": canonical_plan_projection_digest(
                        projection
                    ),
                }
                if projection is not None
                else {}
            ),
        }
    )


def canonical_plan_projection_for_context(
    context: SemanticPropositionTransactionContext,
    value: Mapping[str, Any],
) -> tuple[FrozenCanonicalPropositionEvidencePlan | None, str]:
    """Validate and project the plan selected by the proposal transaction."""

    plans = context.allowed_proposition_evidence_plans
    plan_id = str(value.get("canonical_evidence_plan_id") or "").strip()
    if not plan_id:
        return (
            (None, "canonical_plan_projection_plan_missing")
            if plans is not None
            else (None, "")
        )
    if not isinstance(plans, Mapping):
        return None, "canonical_plan_projection_plan_missing"
    plan = plans.get(plan_id)
    if not isinstance(plan, Mapping):
        return None, "canonical_plan_projection_plan_missing"
    support_by_ref, support_reason = frozen_slot_support_by_ref(
        plan.get("span_refs") or (),
        context.slots,
    )
    if support_reason:
        return None, support_reason
    return frozen_canonical_plan_projection_checked(
        plan,
        context.packed,
        proposition=context.proposition,
        expected_slots=applicable_proposition_slots(context.proposition),
        slot_support_by_ref=support_by_ref,
    )


def canonical_plan_projection_digest(
    projection: FrozenCanonicalPropositionEvidencePlan,
) -> str:
    return canonical_payload_digest(projection.as_dict())


def semantic_audit_input_identity(
    context: SemanticPropositionTransactionContext,
    value: dict[str, Any],
    conclusion: Any,
) -> dict[str, Any]:
    marker = "STRUCTURED CANDIDATE TO VERIFY:\n"
    candidate = (
        context.proposal_prompt.split(marker, 1)[1]
        .split("\n\n", 1)[0]
        .strip()
        .casefold()
        if marker in context.proposal_prompt
        else ""
    )
    return {
        "original_candidate": candidate,
        "candidate_judgment": str(value.get("candidate_judgment") or ""),
        "evidence_relation": str(value.get("evidence_relation") or ""),
        "canonical_evidence_plan_id": str(
            value.get("canonical_evidence_plan_id") or ""
        ),
        "proof_mode": str(value.get("proof_mode") or ""),
        "jointly_complete": value.get("jointly_complete"),
        "each_premise_required": value.get("each_premise_required"),
        "typed_conclusion": {"polarity": str(conclusion.polarity or "")},
        "premise_selection": [
            {
                "span_selector": str(premise.get("span_selector") or ""),
                "proposition_fragment": str(premise.get("proposition_fragment") or ""),
                "supports_slot_ids": list(premise.get("supports_slot_ids") or []),
                "binds_proposition_slots": list(
                    premise.get("binds_proposition_slots") or []
                ),
            }
            for premise in value.get("premises") or []
            if isinstance(premise, dict)
        ],
        "semantic_pack_identity": semantic_pack_identity(context),
    }


def semantic_pack_identity(
    context: SemanticPropositionTransactionContext,
) -> dict[str, str]:
    return {
        "semantic_pack_digest": str(context.semantic_pack_digest or ""),
        "span_universe_digest": str(context.canonical_span_universe_digest or ""),
        "candidate_transaction_id": str(context.candidate_transaction_id or ""),
    }


def transaction_debug(
    context: SemanticPropositionTransactionContext,
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage | None,
    *,
    audit_input: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    proposal_input = {
        "prompt": context.proposal_prompt,
        "question": context.question,
        "packed_evidence": deepcopy(context.packed),
        "required_slots": deepcopy(context.slots),
        "question_proposition": deepcopy(context.proposition.as_dict()),
        "question_proposition_resolution": deepcopy(context.proposition_resolution),
        "semantic_pack_identity": semantic_pack_identity(context),
    }
    return semantic_transaction_debug(
        context.capture_debug_trace,
        proposal,
        audit,
        proposal_model=context.proposal_model,
        audit_model=context.audit_model,
        auditor_relationship=context.auditor_relationship,
        transaction_id=context.transaction_id,
        attempt_namespace=context.attempt_namespace,
        proposal_input=proposal_input,
        audit_input=audit_input,
    )


def transaction_result(
    value: dict[str, Any] | None,
    status: str,
    reason: str,
    diagnostics: dict[str, Any],
    *,
    proposal_calls: int,
    audit_calls: int = 0,
    debug_trace: dict[str, Any] | None = None,
) -> SemanticPropositionTransactionResult:
    finalize_semantic_data_lineage(
        diagnostics,
        status=status,
        reason=reason,
    )
    return SemanticPropositionTransactionResult(
        value=value,
        status=status,
        reason=reason,
        diagnostics=diagnostics,
        proposal_call_count=proposal_calls,
        audit_call_count=audit_calls,
        debug_trace=debug_trace,
    )
