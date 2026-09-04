from __future__ import annotations

from dataclasses import replace
from typing import Any

from .mara_semantic_proof_repair import (
    merge_proof_repair_debug,
    semantic_proposal_binding_digest,
)
from .mara_semantic_proposition_contract import (
    SemanticPropositionTransactionContext,
    SemanticPropositionTransactionResult,
)
from .mara_semantic_proposition_stages import ParsedSemanticStage
from .mara_semantic_recovery_state import unchanged_recovery_transition


def stop_without_reverify(
    context: SemanticPropositionTransactionContext,
    proposal: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    initial_result: SemanticPropositionTransactionResult,
    *,
    reason: str,
    source: str,
) -> SemanticPropositionTransactionResult:
    digest_value = _proposal_binding_digest(proposal)
    transition = unchanged_recovery_transition(
        context.packed,
        context.slots,
        source=source,
        reason=reason,
        semantic_pack_digest=context.semantic_pack_digest,
        proposition_binding_digest=digest_value,
    )
    diagnostics.setdefault("recovery_transitions", []).append(transition)
    diagnostics["recovery_no_progress_count"] = (
        int(diagnostics.get("recovery_no_progress_count") or 0) + 1
    )
    return replace(
        initial_result,
        debug_trace=_repair_debug(
            initial_result,
            None,
            transition,
            None,
            "stopped",
        ),
    )


def finalize_repair_result(
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    repaired: ParsedSemanticStage,
    initial_result: SemanticPropositionTransactionResult,
    repaired_result: SemanticPropositionTransactionResult,
    transition: dict[str, Any],
    repair_kind: str,
) -> SemanticPropositionTransactionResult:
    proposal_calls = (
        proposal.call_count
        if repair_kind == "pruned"
        else proposal.call_count + repaired_result.proposal_call_count
    )
    return replace(
        repaired_result,
        proposal_call_count=proposal_calls,
        audit_call_count=audit.call_count + repaired_result.audit_call_count,
        debug_trace=_repair_debug(
            initial_result,
            repaired_result.debug_trace,
            transition,
            repaired.value,
            repair_kind,
        ),
    )


def _proposal_binding_digest(proposal: ParsedSemanticStage) -> str:
    return semantic_proposal_binding_digest(proposal.value)


def _repair_debug(
    initial_result: SemanticPropositionTransactionResult,
    repaired_debug: dict[str, Any] | None,
    transition: dict[str, Any],
    repaired_value: dict[str, Any] | None,
    repair_kind: str,
) -> dict[str, Any] | None:
    return merge_proof_repair_debug(
        initial_result.debug_trace,
        repaired_debug,
        transition=transition,
        repaired_proposal=repaired_value,
        repair_kind=repair_kind,
    )
