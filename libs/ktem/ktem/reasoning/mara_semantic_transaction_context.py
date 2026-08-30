from __future__ import annotations

from typing import Any

from ktem.docqa.question_proposition import question_proposition_completeness_reason

from .mara_semantic_proposition_contract import (
    SemanticPropositionTransactionContext,
    SemanticPropositionTransactionResult,
    incomplete_proposition_result,
    resolve_proposition_precondition,
)
from .mara_semantic_proposition_debug import semantic_auditor_relationship
from .mara_semantic_transaction_support import transaction_result


def transaction_diagnostics(
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


def release_auditor_failure(
    release_mode: bool,
    relationship: str,
    diagnostics: dict[str, Any],
) -> SemanticPropositionTransactionResult | None:
    if not release_mode or relationship == "distinct_model":
        return None
    reason = "release_conclusion_auditor_not_independent"
    diagnostics["audit_reason"] = reason
    return transaction_result(
        None,
        "failed",
        reason,
        diagnostics,
        proposal_calls=0,
    )


def transaction_preflight(
    proposal_llm: Any,
    audit_llm: Any,
    *,
    proposal_model: str,
    audit_model: str,
    release_mode: bool,
    semantic_pack_digest: str,
) -> tuple[str, dict[str, Any], SemanticPropositionTransactionResult | None]:
    relationship = semantic_auditor_relationship(
        proposal_llm,
        audit_llm,
        proposal_model=proposal_model,
        audit_model=audit_model,
    )
    diagnostics = transaction_diagnostics(relationship, semantic_pack_digest)
    failure = release_auditor_failure(release_mode, relationship, diagnostics)
    return relationship, diagnostics, failure


def prepare_transaction(
    proposal_llm: Any,
    audit_llm: Any,
    *,
    question: str,
    proposal_model: str,
    audit_model: str,
    seed: int,
    release_mode: bool,
    semantic_pack_digest: str,
) -> tuple[
    str,
    dict[str, Any],
    Any | None,
    SemanticPropositionTransactionResult | None,
]:
    relationship, diagnostics, failure = transaction_preflight(
        proposal_llm,
        audit_llm,
        proposal_model=proposal_model,
        audit_model=audit_model,
        release_mode=release_mode,
        semantic_pack_digest=semantic_pack_digest,
    )
    if failure is not None:
        return relationship, diagnostics, None, failure
    resolution = resolve_proposition_precondition(question, diagnostics)
    if not question_proposition_completeness_reason(resolution.proposition):
        return relationship, diagnostics, resolution, None
    failure = incomplete_proposition_result(
        resolution,
        diagnostics,
        proposal_model=proposal_model,
        seed=seed,
        question=question,
        release_mode=release_mode,
        relationship=relationship,
        semantic_pack_digest=semantic_pack_digest,
    )
    return relationship, diagnostics, None, failure


def transaction_context(
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
    canonical_span_universe_digest: str,
    candidate_transaction_id: str,
) -> SemanticPropositionTransactionContext:
    return SemanticPropositionTransactionContext(
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
        canonical_span_universe_digest=canonical_span_universe_digest,
        candidate_transaction_id=candidate_transaction_id,
    )
