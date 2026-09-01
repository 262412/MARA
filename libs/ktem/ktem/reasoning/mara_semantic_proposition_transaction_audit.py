from __future__ import annotations

from typing import Any

from .mara_semantic_entailment_audit import (
    SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
    semantic_entailment_rejection_reason,
)
from .mara_semantic_proposition_contract import (
    SemanticPropositionTransactionContext,
    SemanticPropositionTransactionResult,
    insufficient_semantic_result,
    rejected_semantic_transaction,
)
from .mara_semantic_proposition_stages import (
    ParsedSemanticStage,
    invalid_response_reason,
)
from .mara_semantic_transaction_support import (
    bind_semantic_execution_identity,
    pre_audit_transaction_failure,
    semantic_pack_identity,
    transaction_result,
)


def audit_failure_result(
    context: SemanticPropositionTransactionContext,
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    debug_trace: dict[str, Any] | None,
    *,
    local_consistency: dict[str, Any],
    local_constraint: dict[str, Any],
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
        if audit.call_count == 0 and diagnostics.get("audit_status") == "not_started":
            return pre_audit_transaction_failure(
                proposal,
                audit,
                diagnostics,
                debug_trace,
            )
        if audit.failure_reason == "audit_retry_semantic_identity_changed":
            reason = audit.failure_reason
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
        and diagnostics.get("auditor_override_blocked") is not True
        else semantic_entailment_rejection_reason(audit.value)
    )
    if not rejection_reason and local_constraint.get("status") != "passed":
        rejection_reason = str(
            local_constraint.get("reason") or "local_semantic_relation_rejected"
        )
    if not rejection_reason:
        return None
    diagnostics["audit_reason"] = rejection_reason
    return audit_rejection_result(
        context,
        proposal,
        audit,
        diagnostics,
        debug_trace,
        "semantic_entailment_audit_rejected",
    )


def audit_rejection_result(
    context: SemanticPropositionTransactionContext,
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    debug_trace: dict[str, Any] | None,
    reason: str,
) -> SemanticPropositionTransactionResult:
    rejection_reason = str(diagnostics.get("audit_reason") or reason)
    diagnostics["audit_call_rejection_count"] = (
        int(diagnostics.get("audit_call_rejection_count") or 0) + 1
    )
    diagnostics.update(
        {
            "audit_status": "rejected",
            "audit_execution_status": "parsed",
            "audit_parser_accepted": audit.value is not None,
            "audit_semantic_rejection": audit.value is not None,
            "audit_rejection_reason": rejection_reason,
        }
    )
    diagnostics.setdefault("rejected_transactions", []).append(
        rejected_semantic_transaction(
            proposal.value or {},
            reason=rejection_reason,
            semantic_pack_digest=str(diagnostics.get("semantic_pack_digest") or ""),
            raw_audit_result=audit.value or {},
            local_premise_consistency=dict(
                diagnostics.get("local_premise_consistency") or {}
            ),
            independent_semantic_constraint=dict(
                diagnostics.get("independent_semantic_constraint") or {}
            ),
            semantic_pack_identity=semantic_pack_identity(context),
        )
    )
    value = insufficient_semantic_result(
        context.proposal_model,
        context.seed,
        context.question,
    )
    bind_semantic_execution_identity(value, context)
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
