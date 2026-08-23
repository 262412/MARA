from __future__ import annotations

from typing import Any


def semantic_verifier_failure_metrics(trace: dict[str, Any]) -> dict[str, float]:
    reason = str(trace.get("runtime_semantic_proposition_verifier_reason") or "")
    parse_reason = str(
        trace.get("runtime_semantic_proposition_verifier_parse_failure_reason") or ""
    )
    verifier_status = str(
        trace.get("runtime_semantic_proposition_verifier_status") or ""
    )
    audit_status = str(trace.get("runtime_semantic_entailment_audit_status") or "")
    runtime_authority_status = str(
        trace.get("runtime_semantic_proposition_authority_status") or ""
    )
    audit_verified = audit_status.startswith("verified")
    raw_audit_rejections = _metric_count(
        trace,
        "runtime_semantic_entailment_audit_rejection_count",
        fallback=audit_status == "rejected",
    )
    audited_runtime_rejections = _metric_count(
        trace,
        "runtime_semantic_audit_verified_but_runtime_rejected_count",
        fallback=(
            audit_verified
            and (
                verifier_status == "audit_rejected"
                or runtime_authority_status == "rejected"
            )
        ),
    )
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
        "qasper_semantic_entailment_audit_rejection_count": float(raw_audit_rejections),
        "qasper_semantic_auditor_internal_inconsistency_count": float(
            trace.get("runtime_semantic_auditor_internal_inconsistency_count") or 0
        ),
        "qasper_semantic_proposition_verifier_audit_rejection_count": float(
            verifier_status == "audit_rejected"
        ),
        "qasper_semantic_audit_verified_but_runtime_rejected_count": float(
            audited_runtime_rejections
        ),
    }


def _metric_count(
    trace: dict[str, Any],
    key: str,
    *,
    fallback: bool,
) -> int:
    if key not in trace:
        return int(fallback)
    try:
        return max(0, int(trace.get(key) or 0))
    except (TypeError, ValueError):
        return 0


QASPER_SEMANTIC_AUDIT_UNIQUE_METRIC_KEYS = (
    "qasper_semantic_entailment_audit_rejection_count",
    "qasper_semantic_auditor_internal_inconsistency_count",
    "qasper_semantic_proposition_verifier_audit_rejection_count",
    "qasper_semantic_audit_verified_but_runtime_rejected_count",
)


def unique_semantic_audit_summary(
    predictions: list[dict[str, Any]],
    metrics: list[dict[str, float | None]],
) -> dict[str, int]:
    """Count semantic audit outcomes once per example across route rows."""

    return {
        f"{key.removesuffix('_count')}_unique_example_count": (
            _unique_metric_examples(predictions, metrics, key)
        )
        for key in QASPER_SEMANTIC_AUDIT_UNIQUE_METRIC_KEYS
    }


def _unique_metric_examples(
    predictions: list[dict[str, Any]],
    metrics: list[dict[str, float | None]],
    key: str,
) -> int:
    identities = {
        str(
            prediction.get("example_id")
            or prediction.get("question_id")
            or f"route-record:{index}"
        )
        for index, (prediction, metric) in enumerate(zip(predictions, metrics))
        if float(metric.get(key) or 0.0) > 0
    }
    return len(identities)
