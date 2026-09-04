from __future__ import annotations

from typing import Any


def finance_behavior_violations(
    predictions: list[dict[str, Any]],
) -> list[str]:
    violations: list[str] = []
    answerable = [
        prediction
        for prediction in predictions
        if any(
            str(answer or "").strip().lower()
            not in {"", "unanswerable", "insufficient evidence"}
            for answer in prediction.get("gold_answers") or []
        )
    ]
    expected_abstentions = [
        prediction for prediction in predictions if prediction not in answerable
    ]
    for prediction in answerable:
        metadata = dict(prediction.get("evidence_metadata") or {})
        trace = dict(metadata.get("finance_numeric_trace") or {})
        verification = dict(trace.get("calculation_verification") or {})
        execution = dict(trace.get("calculation_execution") or {})
        if not verification.get("valid") or execution.get("status") != "ok":
            violations.append(
                f"answerable_typed_execution_failed:{prediction.get('example_id')}"
            )
        if str(prediction.get("answer_status") or "") != "answered":
            violations.append(
                f"answerable_typed_execution_not_accepted:{prediction.get('example_id')}"
            )
    for prediction in expected_abstentions:
        if str(prediction.get("answer_status") or "") != "abstained":
            violations.append(
                f"expected_safe_abstention_not_observed:{prediction.get('example_id')}"
            )
        metadata = dict(prediction.get("evidence_metadata") or {})
        if _records(metadata.get("emitted_citation_evidence")):
            violations.append(
                f"abstention_emitted_answer_citation:{prediction.get('example_id')}"
            )
    return violations


def _records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]
