from __future__ import annotations

from typing import Any


def semantic_verifier_failure_metrics(trace: dict[str, Any]) -> dict[str, float]:
    reason = str(trace.get("runtime_semantic_proposition_verifier_reason") or "")
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
    }
