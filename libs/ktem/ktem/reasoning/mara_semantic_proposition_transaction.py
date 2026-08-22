from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from ktem.docqa.boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
)
from ktem.docqa.question_proposition import (
    QuestionProposition,
    build_question_proposition,
    typed_conclusion,
)
from ktem.docqa.semantic_entailment_audit import semantic_entailment_audit_attestation

from .mara_semantic_conclusion_binding import (
    conclusion_audit_binding_reason,
    record_verified_conclusion_audit,
)
from .mara_semantic_entailment_audit import (
    SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
    semantic_entailment_audit_prompt,
    semantic_entailment_rejection_reason,
)
from .mara_semantic_proof_repair import (
    merge_proof_repair_debug,
    proof_rebuild_prompt,
    prune_invalid_premises,
    requires_proof_repair,
)
from .mara_semantic_proposition_debug import (
    semantic_auditor_relationship,
    semantic_transaction_debug,
)
from .mara_semantic_proposition_stages import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
    ParsedSemanticStage,
    audit_diagnostics,
    audit_stage,
    invalid_response_reason,
    proposal_diagnostics,
    proposal_stage,
)


@dataclass(frozen=True)
class SemanticPropositionTransactionResult:
    value: dict[str, Any] | None
    status: str
    reason: str
    diagnostics: dict[str, Any]
    proposal_call_count: int
    audit_call_count: int
    debug_trace: dict[str, Any] | None = None


@dataclass(frozen=True)
class _TransactionContext:
    proposal_llm: Any
    audit_llm: Any
    proposal_prompt: str
    question: str
    packed: list[dict[str, Any]]
    slots: list[dict[str, str]]
    proposition: QuestionProposition
    proposal_model: str
    audit_model: str
    seed: int
    release_mode: bool
    semantic_pack_digest: str
    capture_debug_trace: bool
    auditor_relationship: str


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
) -> SemanticPropositionTransactionResult:
    relationship = semantic_auditor_relationship(
        proposal_llm,
        audit_llm,
        proposal_model=proposal_model,
        audit_model=audit_model,
    )
    diagnostics = {
        "audit_status": "not_started",
        "audit_reason": "",
        "auditor_relationship": relationship,
        "semantic_pack_digest": semantic_pack_digest,
        "recovery_transitions": [],
    }
    if release_mode and relationship == "same_instance":
        diagnostics["audit_reason"] = "release_conclusion_auditor_not_independent"
        return _result(
            None,
            "failed",
            "release_conclusion_auditor_not_independent",
            diagnostics,
            proposal_calls=0,
        )
    context = _TransactionContext(
        proposal_llm=proposal_llm,
        audit_llm=audit_llm,
        proposal_prompt=prompt,
        question=question,
        packed=packed,
        slots=slots,
        proposition=build_question_proposition(question),
        proposal_model=proposal_model,
        audit_model=audit_model,
        seed=seed,
        release_mode=release_mode,
        semantic_pack_digest=semantic_pack_digest,
        capture_debug_trace=capture_debug_trace,
        auditor_relationship=relationship,
    )
    proposal = proposal_stage(
        proposal_llm,
        prompt,
        packed=packed,
        slots=slots,
        model=proposal_model,
        seed=seed,
    )
    diagnostics.update(proposal_diagnostics(proposal))
    return _complete_proposal(context, proposal, diagnostics)


def insufficient_semantic_result(
    model: str, seed: int, question: str = ""
) -> dict[str, Any]:
    result = {
        "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "verdict": "insufficient_evidence",
        "support_mode": "evidence_set",
        "proof_mode": "none",
        "jointly_complete": False,
        "each_premise_required": False,
        "premises": [],
        "verifier": {
            "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
            "model": model,
            "seed": seed,
        },
    }
    if question:
        result["question_proposition"] = build_question_proposition(question).as_dict()
    return result


def _complete_proposal(
    context: _TransactionContext,
    proposal: ParsedSemanticStage,
    diagnostics: dict[str, Any],
) -> SemanticPropositionTransactionResult:
    debug_trace = _transaction_debug(context, proposal, None)
    if proposal.provider_failure_reason:
        return _result(
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
        return _result(
            None,
            "failed",
            reason,
            diagnostics,
            proposal_calls=proposal.call_count,
            debug_trace=debug_trace,
        )
    if proposal.value["verdict"] == "insufficient_evidence":
        _bind_runtime_fields(proposal.value, context)
        diagnostics.update({"audit_status": "not_required", "audit_reason": ""})
        return _result(
            proposal.value,
            "parsed",
            "strict_schema_parsed",
            diagnostics,
            proposal_calls=proposal.call_count,
            debug_trace=debug_trace,
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
    _bind_runtime_fields(value, context)
    conclusion = typed_conclusion(context.proposition, str(value.get("verdict") or ""))
    value["typed_conclusion"] = conclusion.as_dict()
    try:
        prompt = semantic_entailment_audit_prompt(
            context.proposition,
            conclusion,
            str(value.get("proof_mode") or ""),
            value.get("premises") or [],
        )
    except ValueError:
        return _audit_prompt_failure(context, proposal, diagnostics)
    audit = audit_stage(
        context.audit_llm,
        prompt,
        len(value.get("premises") or []),
        seed=context.seed + 1,
    )
    diagnostics.update(audit_diagnostics(audit, model=context.audit_model))
    result = _audit_result(context, proposal, audit, diagnostics)
    if not allow_proof_repair or not requires_proof_repair(audit):
        return result
    return _repair_transaction(context, proposal, audit, diagnostics, result)


def _audit_result(
    context: _TransactionContext,
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    diagnostics: dict[str, Any],
) -> SemanticPropositionTransactionResult:
    debug_trace = _transaction_debug(context, proposal, audit)
    failure = _audit_failure_result(
        context,
        proposal,
        audit,
        diagnostics,
        debug_trace,
    )
    if failure is not None:
        return failure
    value = proposal.value or {}
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
    return _result(
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
) -> SemanticPropositionTransactionResult | None:
    if audit.provider_failure_reason:
        return _result(
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
        return _result(
            None,
            "failed",
            reason,
            diagnostics,
            proposal_calls=proposal.call_count,
            audit_calls=audit.call_count,
            debug_trace=debug_trace,
        )
    rejection_reason = semantic_entailment_rejection_reason(audit.value)
    if not rejection_reason:
        return None
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
    value = insufficient_semantic_result(
        context.proposal_model, context.seed, context.question
    )
    _bind_runtime_fields(value, context)
    return _result(
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
) -> SemanticPropositionTransactionResult:
    repaired = prune_invalid_premises(proposal, audit, context.slots)
    repair_kind = "pruned" if repaired is not None else "rebuilt"
    transition = {
        "from": "semantic_audit",
        "to": "proof_repair",
        "reason": "premise_false_jointly_entails_true",
        "outcome": "pruned" if repaired is not None else "rebuild_required",
    }
    diagnostics.setdefault("recovery_transitions", []).append(transition)
    diagnostics["proof_repair_count"] = (
        int(diagnostics.get("proof_repair_count") or 0) + 1
    )
    if repaired is None:
        repaired, terminal = _rebuild_proposal(
            context, proposal, audit, diagnostics, initial_result, transition
        )
        if terminal is not None:
            return terminal
    assert repaired is not None
    repaired_result = _audit_transaction(
        replace(context, seed=context.seed + 10),
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
                "audit_reason": "premise_false_jointly_entails_true",
            }
        )
    return _finalize_repair_result(
        proposal,
        audit,
        repaired,
        initial_result,
        repaired_result,
        transition,
        repair_kind,
    )


def _rebuild_proposal(
    context: _TransactionContext,
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    initial_result: SemanticPropositionTransactionResult,
    transition: dict[str, Any],
) -> tuple[ParsedSemanticStage | None, SemanticPropositionTransactionResult | None]:
    prompt = proof_rebuild_prompt(context.proposal_prompt, audit)
    if prompt is None:
        transition["outcome"] = "rebuild_prompt_bound_exceeded"
        return None, replace(
            initial_result,
            debug_trace=_repair_debug(
                initial_result, None, transition, None, "rebuilt"
            ),
        )
    repaired = proposal_stage(
        context.proposal_llm,
        prompt,
        packed=context.packed,
        slots=context.slots,
        model=context.proposal_model,
        seed=context.seed + 10,
    )
    diagnostics["proof_rebuild_count"] = (
        int(diagnostics.get("proof_rebuild_count") or 0) + 1
    )
    diagnostics["proof_rebuild_proposal_call_count"] = repaired.call_count
    if repaired.value is None:
        transition["outcome"] = "rebuild_failed"
        repaired_debug = _transaction_debug(context, repaired, None)
        return None, replace(
            initial_result,
            proposal_call_count=proposal.call_count + repaired.call_count,
            debug_trace=_repair_debug(
                initial_result, repaired_debug, transition, None, "rebuilt"
            ),
        )
    if repaired.value.get("verdict") != "insufficient_evidence":
        transition["outcome"] = "rebuilt"
        return repaired, None
    transition["outcome"] = "rebuilt_as_insufficient"
    _bind_runtime_fields(repaired.value, replace(context, seed=context.seed + 10))
    repaired_debug = _transaction_debug(context, repaired, None)
    return None, _result(
        repaired.value,
        "parsed",
        "proof_rebuild_insufficient_evidence",
        diagnostics,
        proposal_calls=proposal.call_count + repaired.call_count,
        audit_calls=audit.call_count,
        debug_trace=_repair_debug(
            initial_result,
            repaired_debug,
            transition,
            repaired.value,
            "rebuilt",
        ),
    )


def _finalize_repair_result(
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


def _audit_prompt_failure(
    context: _TransactionContext,
    proposal: ParsedSemanticStage,
    diagnostics: dict[str, Any],
) -> SemanticPropositionTransactionResult:
    diagnostics.update(
        {"audit_status": "failed", "audit_reason": "audit_prompt_bound_exceeded"}
    )
    return _result(
        None,
        "failed",
        "audit_prompt_bound_exceeded",
        diagnostics,
        proposal_calls=proposal.call_count,
        debug_trace=_transaction_debug(context, proposal, None),
    )


def _bind_runtime_fields(value: dict[str, Any], context: _TransactionContext) -> None:
    value["question_proposition"] = context.proposition.as_dict()
    value["verifier"].update(
        {
            "release_mode": context.release_mode,
            "auditor_relationship": context.auditor_relationship,
            "semantic_pack_digest": context.semantic_pack_digest,
        }
    )


def _transaction_debug(
    context: _TransactionContext,
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


def _result(
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
