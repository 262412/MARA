from __future__ import annotations

from copy import deepcopy
from typing import Any


def semantic_proposition_verifier_trace_fields(
    prediction: dict[str, Any],
) -> dict[str, Any]:
    trace = _semantic_proposition_verifier_trace(prediction)
    return {
        **_semantic_verifier_runtime_trace_fields(trace),
        **_semantic_proposal_response_trace_fields(trace),
        **_semantic_entailment_audit_trace_fields(trace),
    }


def _semantic_proposition_verifier_trace(
    prediction: dict[str, Any],
) -> dict[str, Any]:
    bundle = prediction.get("engine_terminal_evidence_bundle")
    bundle = bundle if isinstance(bundle, dict) else {}
    metadata = bundle.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    trace = metadata.get("semantic_proposition_verifier")
    return trace if isinstance(trace, dict) else {}


def _semantic_verifier_runtime_trace_fields(
    trace: dict[str, Any],
) -> dict[str, Any]:
    return {
        "runtime_semantic_proposition_verifier_contract_id": str(
            trace.get("contract_id") or ""
        ),
        "runtime_semantic_proposition_verifier_status": str(trace.get("status") or ""),
        "runtime_semantic_proposition_verifier_reason": str(trace.get("reason") or ""),
        "runtime_semantic_proposition_verifier_model_call_count": _nonnegative_int(
            trace.get("actual_model_call_count")
        ),
        "runtime_semantic_proposition_verifier_proposal_call_count": (
            _nonnegative_int(trace.get("proposal_model_call_count"))
        ),
        "runtime_semantic_entailment_audit_call_count": _nonnegative_int(
            trace.get("audit_model_call_count")
        ),
        "runtime_semantic_proposition_verifier_available_evidence_count": (
            _nonnegative_int(trace.get("available_evidence_count"))
        ),
        "runtime_semantic_proposition_verifier_packed_evidence_count": (
            _nonnegative_int(trace.get("packed_evidence_count"))
        ),
        "runtime_semantic_proposition_verifier_evidence_item_char_limit": (
            _nonnegative_int(trace.get("evidence_item_char_limit"))
        ),
        "runtime_semantic_proposition_verifier_estimated_input_token_budget": (
            _nonnegative_int(trace.get("estimated_input_token_budget"))
        ),
        "runtime_semantic_proposition_verifier_estimated_input_tokens": (
            _nonnegative_int(trace.get("estimated_input_tokens"))
        ),
        "runtime_semantic_proposition_verifier_minimum_model_context_tokens": (
            _nonnegative_int(trace.get("minimum_model_context_tokens"))
        ),
        "runtime_semantic_proposition_verifier_packed_evidence_chars": (
            _nonnegative_int(trace.get("packed_evidence_chars"))
        ),
        "runtime_semantic_proposition_verifier_dropped_evidence_count": (
            _nonnegative_int(trace.get("dropped_evidence_count"))
        ),
        "runtime_semantic_proposition_verifier_truncated_evidence_count": (
            _nonnegative_int(trace.get("truncated_evidence_count"))
        ),
        "runtime_semantic_proposition_verifier_required_slot_count": _nonnegative_int(
            trace.get("required_slot_count")
        ),
        "runtime_semantic_proposition_verifier_prompt_chars": _nonnegative_int(
            trace.get("prompt_chars")
        ),
        "runtime_semantic_proposition_verifier_max_prompt_chars": _nonnegative_int(
            trace.get("max_prompt_chars")
        ),
        "runtime_semantic_proposition_verifier_max_output_tokens": _nonnegative_int(
            trace.get("max_output_tokens")
        ),
        "runtime_semantic_proposition_verifier_cache_hit": bool(trace.get("cache_hit")),
        **_semantic_verifier_contract_trace_fields(trace),
        "runtime_semantic_proposition_verifier_verdict": str(
            trace.get("verdict") or ""
        ),
    }


def _semantic_verifier_contract_trace_fields(
    trace: dict[str, Any],
) -> dict[str, Any]:
    return {
        "runtime_semantic_proposition_cache_source": str(
            trace.get("cache_source") or ""
        ),
        "runtime_semantic_proposition_cache_source_event_index": _nonnegative_int(
            trace.get("cache_source_event_index")
        ),
        "runtime_semantic_pack_digest": str(trace.get("semantic_pack_digest") or ""),
        "runtime_semantic_question_proposition": deepcopy(
            trace.get("question_proposition") or {}
        ),
        "runtime_semantic_question_proposition_resolution": deepcopy(
            trace.get("question_proposition_resolution") or {}
        ),
        "runtime_semantic_proof_mode": str(trace.get("proof_mode") or ""),
        "runtime_semantic_typed_conclusion": deepcopy(
            trace.get("typed_conclusion") or {}
        ),
        "runtime_semantic_auditor_relationship": str(
            trace.get("auditor_relationship") or ""
        ),
        "runtime_semantic_recovery_transitions": deepcopy(
            trace.get("recovery_transitions") or []
        ),
        "runtime_semantic_conclusion_audit": deepcopy(
            trace.get("conclusion_audit") or {}
        ),
        "runtime_semantic_polarity_contradiction_check": deepcopy(
            trace.get("polarity_contradiction_check") or {}
        ),
        "runtime_semantic_rejected_transactions": deepcopy(
            trace.get("rejected_transactions") or []
        ),
        "runtime_semantic_auditor_internal_inconsistency": bool(
            trace.get("auditor_internal_inconsistency")
        ),
        "runtime_semantic_auditor_internal_inconsistency_count": (
            _nonnegative_int(trace.get("auditor_internal_inconsistency_count"))
        ),
        "runtime_semantic_local_premise_consistency": deepcopy(
            trace.get("local_premise_consistency") or {}
        ),
        "runtime_semantic_local_premise_consistency_history": deepcopy(
            trace.get("local_premise_consistency_history") or []
        ),
        "runtime_semantic_entailment_audit_rejection_count": _nonnegative_int(
            trace.get("audit_call_rejection_count")
        ),
        "runtime_semantic_audit_verified_but_runtime_rejected_count": (
            _nonnegative_int(trace.get("audit_verified_but_runtime_rejected_count"))
        ),
        "runtime_semantic_runtime_contract_rejection_count": _nonnegative_int(
            trace.get("runtime_contract_rejection_count")
        ),
        "runtime_semantic_proof_digest_before": str(
            trace.get("semantic_proof_digest_before") or ""
        ),
        "runtime_semantic_proof_digest_after": str(
            trace.get("semantic_proof_digest_after") or ""
        ),
        "runtime_semantic_proof_digest_changed": bool(
            trace.get("semantic_proof_digest_changed")
        ),
    }


def _semantic_proposal_response_trace_fields(
    trace: dict[str, Any],
) -> dict[str, Any]:
    return {
        "runtime_semantic_proposition_verifier_proposal_retry_count": (
            _nonnegative_int(trace.get("proposal_retry_count"))
        ),
        "runtime_semantic_proposition_verifier_initial_parse_failure_reason": str(
            trace.get("initial_parse_failure_reason") or ""
        ),
        "runtime_semantic_proposition_verifier_parse_failure_reason": str(
            trace.get("parse_failure_reason") or ""
        ),
        "runtime_semantic_proposition_verifier_finish_reason": str(
            trace.get("response_finish_reason") or ""
        ),
        "runtime_semantic_proposition_verifier_completion_tokens": _nonnegative_int(
            trace.get("response_completion_tokens")
        ),
        "runtime_semantic_proposition_verifier_response_chars": _nonnegative_int(
            trace.get("response_chars")
        ),
    }


def _semantic_entailment_audit_trace_fields(
    trace: dict[str, Any],
) -> dict[str, Any]:
    return {
        "runtime_semantic_entailment_audit_contract_id": str(
            trace.get("audit_contract_id") or ""
        ),
        "runtime_semantic_entailment_audit_model": str(trace.get("audit_model") or ""),
        "runtime_semantic_entailment_audit_status": str(
            trace.get("audit_status") or ""
        ),
        "runtime_semantic_entailment_audit_reason": str(
            trace.get("audit_reason") or ""
        ),
        "runtime_semantic_entailment_audit_retry_count": _nonnegative_int(
            trace.get("audit_retry_count")
        ),
        "runtime_semantic_entailment_audit_parse_failure_reason": str(
            trace.get("audit_parse_failure_reason") or ""
        ),
        "runtime_semantic_entailment_audit_finish_reason": str(
            trace.get("audit_response_finish_reason") or ""
        ),
        "runtime_semantic_entailment_audit_completion_tokens": _nonnegative_int(
            trace.get("audit_response_completion_tokens")
        ),
        "runtime_semantic_entailment_audit_response_chars": _nonnegative_int(
            trace.get("audit_response_chars")
        ),
        "runtime_semantic_entailment_audit_proposal_digest": str(
            trace.get("audit_proposal_digest") or ""
        ),
    }


def semantic_proposition_authority_trace_fields(
    prediction: dict[str, Any],
) -> dict[str, Any]:
    bundle = prediction.get("engine_terminal_evidence_bundle")
    bundle = bundle if isinstance(bundle, dict) else {}
    metadata = bundle.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    trace = metadata.get("semantic_proposition_authority")
    trace = trace if isinstance(trace, dict) else {}
    return {
        "runtime_semantic_proposition_authority_contract_id": str(
            trace.get("contract_id") or ""
        ),
        "runtime_semantic_proposition_authority_status": str(trace.get("status") or ""),
        "runtime_semantic_proposition_authority_reason": str(trace.get("reason") or ""),
        "runtime_semantic_proposition_authority_premise_count": _nonnegative_int(
            trace.get("premise_count")
        ),
        "runtime_semantic_proposition_authority_derivation_id": str(
            trace.get("derivation_id") or ""
        ),
        "runtime_semantic_proposition_authority_proof_mode": str(
            trace.get("proof_mode") or ""
        ),
        "runtime_semantic_proposition_authority_question_proposition": deepcopy(
            trace.get("question_proposition") or {}
        ),
        "runtime_semantic_proposition_authority_typed_conclusion": deepcopy(
            trace.get("typed_conclusion") or {}
        ),
        "runtime_semantic_proposition_authority_auditor_relationship": str(
            trace.get("auditor_relationship") or ""
        ),
        "runtime_semantic_proposition_authority_conclusion_audit": deepcopy(
            trace.get("conclusion_audit") or {}
        ),
        "runtime_semantic_proposition_authority_polarity_contradiction_check": (
            deepcopy(trace.get("polarity_contradiction_check") or {})
        ),
        "runtime_semantic_proposition_authority_audited_typed_conclusion": (
            deepcopy(trace.get("audited_typed_conclusion") or {})
        ),
        "runtime_semantic_proposition_authority_audited_conclusion_audit": (
            deepcopy(trace.get("audited_conclusion_audit") or {})
        ),
        "runtime_semantic_proposition_authority_audit_verified_but_runtime_rejected": (
            bool(trace.get("audit_verified_but_runtime_rejected"))
        ),
        "runtime_semantic_proposition_authority_pack_digest": str(
            trace.get("semantic_pack_digest") or ""
        ),
    }


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
