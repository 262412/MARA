from __future__ import annotations

from typing import Any


def semantic_verifier_failure_metrics(trace: dict[str, Any]) -> dict[str, float]:
    reason = str(trace.get("runtime_semantic_proposition_verifier_reason") or "")
    parse_reason = str(
        trace.get("runtime_semantic_proposition_verifier_parse_failure_reason") or ""
    )
    audit_status = str(trace.get("runtime_semantic_entailment_audit_status") or "")
    return {
        "qasper_semantic_proposition_verifier_failure_count": float(
            trace.get("runtime_semantic_proposition_verifier_status")
            in {"failed", "cached_failure"}
        ),
        "qasper_semantic_proposition_verifier_context_overflow_count": float(
            reason == "provider_context_length_exceeded"
        ),
        "qasper_semantic_proposition_verifier_schema_unsupported_count": float(
            reason == "provider_response_schema_unsupported"
        ),
        "qasper_semantic_proposition_output_truncation_count": float(
            reason == "provider_output_truncated"
        ),
        "qasper_semantic_proposition_json_decode_failure_count": float(
            reason == "invalid_model_json" and parse_reason == "json_decode_error"
        ),
        "qasper_semantic_proposition_parse_contract_rejection_count": float(
            reason == "invalid_model_json"
            and bool(parse_reason)
            and parse_reason != "json_decode_error"
        ),
        "qasper_semantic_entailment_audit_call_count": float(
            trace.get("runtime_semantic_entailment_audit_call_count") or 0
        ),
        "qasper_semantic_entailment_audit_failure_count": float(
            audit_status == "failed"
        ),
        "qasper_semantic_entailment_audit_rejection_count": float(
            audit_status == "rejected"
        ),
    }
