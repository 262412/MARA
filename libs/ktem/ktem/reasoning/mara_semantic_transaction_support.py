from __future__ import annotations

from typing import Any

from .mara_semantic_proposition_contract import (
    SemanticPropositionTransactionContext,
    SemanticPropositionTransactionResult,
)
from .mara_semantic_proposition_debug import semantic_transaction_debug
from .mara_semantic_proposition_stages import ParsedSemanticStage


def audit_prompt_failure(
    context: SemanticPropositionTransactionContext,
    proposal: ParsedSemanticStage,
    diagnostics: dict[str, Any],
) -> SemanticPropositionTransactionResult:
    diagnostics.update(
        {"audit_status": "failed", "audit_reason": "audit_prompt_bound_exceeded"}
    )
    return transaction_result(
        None,
        "failed",
        "audit_prompt_bound_exceeded",
        diagnostics,
        proposal_calls=proposal.call_count,
        debug_trace=transaction_debug(context, proposal, None),
    )


def bind_semantic_runtime_fields(
    value: dict[str, Any],
    context: SemanticPropositionTransactionContext,
) -> None:
    value["question_proposition"] = context.proposition.as_dict()
    value["question_proposition_resolution"] = dict(context.proposition_resolution)
    value["verifier"].update(
        {
            "release_mode": context.release_mode,
            "auditor_relationship": context.auditor_relationship,
            "semantic_pack_digest": context.semantic_pack_digest,
        }
    )


def transaction_debug(
    context: SemanticPropositionTransactionContext,
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage | None,
) -> dict[str, Any] | None:
    return semantic_transaction_debug(
        context.capture_debug_trace,
        proposal,
        audit,
        proposal_model=context.proposal_model,
        audit_model=context.audit_model,
        auditor_relationship=context.auditor_relationship,
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
    return SemanticPropositionTransactionResult(
        value=value,
        status=status,
        reason=reason,
        diagnostics=diagnostics,
        proposal_call_count=proposal_calls,
        audit_call_count=audit_calls,
        debug_trace=debug_trace,
    )
