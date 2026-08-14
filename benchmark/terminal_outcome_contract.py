from __future__ import annotations

from typing import Any

from ktem.docqa.terminal_semantic_commit import (
    TERMINAL_OUTCOMES,
    terminal_commit_outcome,
    terminal_commit_projection_present,
)

BENCHMARK_OUTCOME_CLASSES = (
    "answered",
    "true_abstention",
    "false_abstention",
    "execution_failed",
    "timeout",
    "cancelled",
    "unclassified",
)


def terminal_outcome_record(prediction: dict[str, Any]) -> dict[str, Any]:
    state = prediction.get("engine_terminal_state")
    applicable = bool(
        isinstance(state, dict)
        and state.get("contract_id") == "engine_terminal_state.v1"
    )
    commit = prediction.get("engine_terminal_commit") or prediction.get(
        "terminal_semantic_commit"
    )
    projection_present = terminal_commit_projection_present(commit)
    outcome = terminal_commit_outcome(commit) if projection_present else ""
    reason = str(commit.get("outcome_reason") or "") if isinstance(commit, dict) else ""
    record = {
        "applicable": applicable,
        "projection_present": projection_present,
        "contract_violation": bool(applicable and not projection_present),
        "outcome": outcome,
        "reason": reason,
    }
    record.update({value: int(outcome == value) for value in TERMINAL_OUTCOMES})
    return record


def apply_terminal_outcome_record(prediction: dict[str, Any]) -> dict[str, Any]:
    record = terminal_outcome_record(prediction)
    prediction["terminal_outcome"] = record["outcome"]
    prediction["terminal_outcome_reason"] = record["reason"]
    prediction["terminal_outcome_contract_violation"] = record["contract_violation"]
    return record


def benchmark_outcome_classification(prediction: dict[str, Any]) -> str:
    outcome = str(terminal_outcome_record(prediction)["outcome"] or "")
    if outcome == "safe_abstention":
        return (
            "false_abstention"
            if _is_false_abstention(prediction)
            else "true_abstention"
        )
    if outcome in {"answered", "execution_failed", "timeout", "cancelled"}:
        return outcome
    return "unclassified"


def apply_benchmark_outcome_classification(prediction: dict[str, Any]) -> str:
    classification = benchmark_outcome_classification(prediction)
    prediction["terminal_outcome_classification"] = classification
    return classification


def terminal_outcome_summary_fields(
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    counts = {value: 0 for value in BENCHMARK_OUTCOME_CLASSES}
    contract_violations = 0
    missing = 0
    for prediction in predictions:
        record = terminal_outcome_record(prediction)
        classification = benchmark_outcome_classification(prediction)
        counts[classification] += 1
        contract_violations += int(record["contract_violation"])
        missing += int(not record["outcome"])
    return {
        "terminal_outcome_counts": counts,
        "terminal_outcome_contract_violation_count": contract_violations,
        "terminal_outcome_missing_count": missing,
    }


def terminal_outcome_route_fields(
    predictions: list[dict[str, Any]],
) -> dict[str, int]:
    summary = terminal_outcome_summary_fields(predictions)
    counts = summary["terminal_outcome_counts"]
    fields = {
        f"num_terminal_{classification}": int(counts[classification])
        for classification in BENCHMARK_OUTCOME_CLASSES
    }
    fields["terminal_outcome_contract_violation_count"] = int(
        summary["terminal_outcome_contract_violation_count"]
    )
    return fields


def _is_false_abstention(prediction: dict[str, Any]) -> bool:
    metrics = prediction.get("metrics")
    observability = prediction.get("verifier_observability")
    values = (
        metrics.get("false_abstention") if isinstance(metrics, dict) else None,
        observability.get("false_abstention")
        if isinstance(observability, dict)
        else None,
    )
    for value in values:
        try:
            if float(value or 0.0) > 0.0:
                return True
        except (TypeError, ValueError):
            continue
    return False
