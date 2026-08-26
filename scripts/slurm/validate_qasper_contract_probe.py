from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmark.artifact_publication import atomic_write_json, file_sha256
from benchmark.jsonl import read_jsonl
from scripts.slurm.qasper_debug_contract import (
    qasper_debug_audit_extensions,
    qasper_debug_behavior_violations,
)
from scripts.slurm.qasper_debug_contract_probe_artifact import (
    _MODEL_CONTRACT,
    _assert_live_coverage,
    _observed_state_evidence,
)

CONTRACT = "qasper_provider_contract_probe_audit.v1"
_HARD_GATES = {
    "qasper_contract_probe_structural_state_matrix_complete": 1.0,
    "qasper_contract_probe_required_online_states_complete": 1.0,
    "qasper_contract_probe_online_auditor_attempt_missing_count": 0.0,
    "qasper_contract_probe_online_verifier_missing_count": 0.0,
    "qasper_contract_probe_unexpected_false_abstention_count": 0.0,
    "qasper_unexpected_unknown_assessment_count": 0.0,
    "qasper_candidate_raw_identity_mismatch_count": 0.0,
    "qasper_empty_candidate_audit_count": 0.0,
    "qasper_empty_typed_conclusion_count": 0.0,
    "qasper_required_slot_unverified_count": 0.0,
    "qasper_reverify_without_semantic_state_change_count": 0.0,
}
_LIVE_COVERAGE_GATE = "qasper_contract_probe_live_coverage_assertion_complete"
_EXECUTION_GATE = "qasper_contract_probe_execution_complete"
_BEHAVIOR_GATE = "qasper_contract_probe_behavior_violations"


def _is_live_probe_artifact(predictions: list[dict[str, Any]]) -> bool:
    return any(row.get("contract_id") == _MODEL_CONTRACT for row in predictions)


def _exception_evidence(exc: BaseException) -> dict[str, str]:
    return {
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
    }


def _failed_exception_audit(
    predictions_path: Path,
    output_path: Path,
    predictions: list[dict[str, Any]],
    *,
    source_sha256: str | None,
    failure_evidence: dict[str, Any] | None,
    exc: BaseException,
) -> dict[str, Any]:
    evidence = dict(failure_evidence or {})
    evidence["exception"] = _exception_evidence(exc)
    observed_state = _observed_state_evidence(predictions)
    failed_gates = [_EXECUTION_GATE]
    failure_details = {
        "observed_state": observed_state,
        **evidence,
    }
    lane_audit = {
        "lane": "contract_probe",
        "status": "failed",
        "prediction_count": len(predictions),
        "failed_gates": failed_gates,
        "failure_evidence": failure_details,
    }
    return {
        "contract": CONTRACT,
        "status": "failed",
        "source": str(predictions_path.resolve()),
        "source_sha256": source_sha256,
        "prediction_count": len(predictions),
        "replacement_candidate_allowed": False,
        "behavior_violations": [],
        "hard_gates": {
            _EXECUTION_GATE: {
                "value": 0.0,
                "expected": 1.0,
                "passed": False,
            }
        },
        "failed_gates": failed_gates,
        "contract_probe_audit": lane_audit,
        "structural_state_matrix": {},
        "debug_gate_metrics": {},
        "failure_evidence": failure_details,
        "audit_output": str(output_path.resolve()),
    }


def _coverage_failure(
    predictions: list[dict[str, Any]],
) -> dict[str, str] | None:
    if not _is_live_probe_artifact(predictions):
        return None
    try:
        _assert_live_coverage(predictions)
    except RuntimeError as exc:
        return _exception_evidence(exc)
    return None


def _hard_gates(
    metrics: dict[str, Any],
    predictions: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, str] | None]:
    hard_gates = {
        name: {
            "value": metrics.get(name),
            "expected": expected,
            "passed": metrics.get(name) is not None
            and float(metrics[name]) == expected,
        }
        for name, expected in _HARD_GATES.items()
    }
    coverage_failure = _coverage_failure(predictions)
    if _is_live_probe_artifact(predictions):
        hard_gates[_LIVE_COVERAGE_GATE] = {
            "value": 0.0 if coverage_failure else 1.0,
            "expected": 1.0,
            "passed": coverage_failure is None,
        }
    return hard_gates, coverage_failure


def _evaluate_probe(
    predictions: list[dict[str, Any]],
    *,
    failure_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    extensions = qasper_debug_audit_extensions(
        [],
        contract_probe_predictions=predictions,
    )
    metrics = dict(extensions.get("debug_gate_metrics") or {})
    hard_gates, coverage_failure = _hard_gates(metrics, predictions)
    failed_gates = [
        name for name, result in hard_gates.items() if result["passed"] is not True
    ]
    violations = qasper_debug_behavior_violations(
        [],
        contract_probe_predictions=predictions,
    )
    lane_audit = dict(extensions.get("contract_probe_audit") or {})
    combined_failure_evidence = dict(failure_evidence or {})
    if coverage_failure is not None:
        combined_failure_evidence["coverage_exception"] = coverage_failure
    if combined_failure_evidence:
        hard_gates[_EXECUTION_GATE] = {
            "value": 0.0,
            "expected": 1.0,
            "passed": False,
        }
        failed_gates.append(_EXECUTION_GATE)
        lane_audit["status"] = "failed"
    if violations:
        hard_gates[_BEHAVIOR_GATE] = {
            "value": float(len(violations)),
            "expected": 0.0,
            "passed": False,
        }
        failed_gates.append(_BEHAVIOR_GATE)
    status = (
        "passed"
        if predictions
        and lane_audit.get("status") == "passed"
        and not violations
        and not failed_gates
        else "failed"
    )
    observed_state = _observed_state_evidence(predictions)
    failure_details = {
        "observed_state": observed_state,
        **combined_failure_evidence,
    }
    if violations:
        failure_details["behavior_violations"] = list(violations)
    lane_audit["status"] = status
    lane_audit["failed_gates"] = list(failed_gates)
    lane_audit["failure_evidence"] = failure_details
    return {
        "status": status,
        "behavior_violations": violations,
        "hard_gates": hard_gates,
        "failed_gates": failed_gates,
        "contract_probe_audit": lane_audit,
        "structural_state_matrix": extensions.get("structural_state_matrix") or {},
        "debug_gate_metrics": metrics,
        "failure_evidence": failure_details,
    }


def _audit_payload(
    predictions_path: Path,
    output_path: Path,
    predictions: list[dict[str, Any]],
    *,
    source_sha256: str,
    failure_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    evaluated = _evaluate_probe(
        predictions,
        failure_evidence=failure_evidence,
    )
    return {
        "contract": CONTRACT,
        "status": evaluated["status"],
        "source": str(predictions_path.resolve()),
        "source_sha256": source_sha256,
        "prediction_count": len(predictions),
        "replacement_candidate_allowed": False,
        **{key: value for key, value in evaluated.items() if key != "status"},
        "audit_output": str(output_path.resolve()),
    }


def persist_failed_contract_probe_audit(
    predictions_path: Path,
    *,
    output_path: Path,
    failure_evidence: dict[str, Any],
    evaluate_gates: bool = True,
) -> dict[str, Any]:
    """Atomically publish fail-closed evidence without raising a hard gate."""

    predictions: list[dict[str, Any]] = []
    source_sha256: str | None = None
    try:
        predictions = [
            row for row in read_jsonl(predictions_path) if isinstance(row, dict)
        ]
        source_sha256 = file_sha256(predictions_path)
        if evaluate_gates:
            audit = _audit_payload(
                predictions_path,
                output_path,
                predictions,
                source_sha256=source_sha256,
                failure_evidence=failure_evidence,
            )
        else:
            audit = _failed_exception_audit(
                predictions_path,
                output_path,
                predictions,
                source_sha256=source_sha256,
                failure_evidence=failure_evidence,
                exc=RuntimeError("contract probe hard gate not completed"),
            )
    except (
        AttributeError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        audit = _failed_exception_audit(
            predictions_path,
            output_path,
            predictions,
            source_sha256=source_sha256,
            failure_evidence=failure_evidence,
            exc=exc,
        )
    if audit["status"] != "failed":
        raise ValueError("fail-closed contract probe audit unexpectedly passed")
    atomic_write_json(output_path, audit)
    return audit


def validate_contract_probe(
    predictions_path: Path,
    *,
    output_path: Path,
    failure_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    predictions: list[dict[str, Any]] = []
    source_sha256: str | None = None
    audit_written = False
    try:
        predictions = [
            row for row in read_jsonl(predictions_path) if isinstance(row, dict)
        ]
        source_sha256 = file_sha256(predictions_path)
        audit = _audit_payload(
            predictions_path,
            output_path,
            predictions,
            source_sha256=source_sha256,
            failure_evidence=failure_evidence,
        )
        atomic_write_json(output_path, audit)
        audit_written = True
        if audit["status"] != "passed":
            details = [*audit["behavior_violations"], *audit["failed_gates"]]
            raise ValueError("provider contract probe failed: " + ",".join(details))
        return audit
    except Exception as exc:  # noqa: BLE001 - failed audit is fail-closed evidence
        if not audit_written:
            atomic_write_json(
                output_path,
                _failed_exception_audit(
                    predictions_path,
                    output_path,
                    predictions,
                    source_sha256=source_sha256,
                    failure_evidence=failure_evidence,
                    exc=exc,
                ),
            )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fail-closed audit for live QASPER provider contract probes."
    )
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        audit = validate_contract_probe(
            args.predictions.resolve(),
            output_path=args.output.resolve(),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"contract_probe_status={audit['status']}")
    print(f"contract_probe_audit={args.output.resolve()}")


if __name__ == "__main__":
    main()
