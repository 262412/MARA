from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmark.artifact_publication import atomic_write_json, file_sha256
from benchmark.jsonl import read_jsonl
from scripts.slurm.qasper_debug_contract_probe_artifact import (
    _assert_live_coverage,
    _assert_pre_audit_case,
    _observed_state_evidence,
    _provider_identity_violations,
)
from scripts.slurm.qasper_debug_contract_probe_cases import (
    NATURAL_QUALITY_PRE_AUDIT_CASES,
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
    "qasper_controlled_candidate_transport_mismatch_count": 0.0,
    "qasper_empty_candidate_audit_count": 0.0,
    "qasper_empty_typed_conclusion_count": 0.0,
    "qasper_required_slot_unverified_count": 0.0,
    "qasper_reverify_without_semantic_state_change_count": 0.0,
}
_LIVE_COVERAGE_GATE = "qasper_contract_probe_live_coverage_assertion_complete"
_PROVIDER_HETEROGENEITY_GATE = "qasper_contract_probe_provider_heterogeneity_complete"
_EXECUTION_GATE = "qasper_contract_probe_execution_complete"
_BEHAVIOR_GATE = "qasper_contract_probe_behavior_violations"
_PRE_AUDIT_COVERAGE_GATE = "qasper_contract_probe_pre_audit_case_coverage_complete"
_PRE_AUDIT_TERMINAL_GATE = "qasper_contract_probe_pre_audit_terminalization_complete"


def _is_live_probe_artifact(predictions: list[dict[str, Any]]) -> bool:
    return any(
        str(row.get("contract_id") or "").startswith(
            "qasper_contract_probe_live_model."
        )
        for row in predictions
    )


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
    provider_identity_violations = _provider_identity_failure(predictions)
    if "heterogeneous contract probe" in str(exc).casefold():
        provider_identity_violations = [
            {
                "reason": "provider_configuration_rejected",
                "exception": _exception_evidence(exc),
            }
        ]
    failed_gates = [_EXECUTION_GATE]
    if provider_identity_violations:
        failed_gates.append(_PROVIDER_HETEROGENEITY_GATE)
    failure_details = {
        "observed_state": observed_state,
        "provider_identity_violations": provider_identity_violations,
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
            },
            _PROVIDER_HETEROGENEITY_GATE: {
                "value": 0.0 if provider_identity_violations else 1.0,
                "expected": 1.0,
                "passed": not provider_identity_violations,
            },
        },
        "failed_gates": failed_gates,
        "contract_probe_audit": lane_audit,
        "structural_state_matrix": {},
        "debug_gate_metrics": {},
        "failure_evidence": failure_details,
        "provider_identity_violations": provider_identity_violations,
        "audit_output": str(output_path.resolve()),
    }


def _provider_identity_failure(
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not _is_live_probe_artifact(predictions):
        return []
    failures: list[dict[str, Any]] = []
    for row in predictions:
        violations = _provider_identity_violations(row)
        if violations:
            failures.append(
                {
                    "example_id": str(row.get("example_id") or ""),
                    "violations": violations,
                }
            )
    return failures


def _provider_configuration_failure(
    failure_evidence: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    evidence = failure_evidence or {}
    exception = evidence.get("probe_exception")
    exception = exception if isinstance(exception, dict) else {}
    message = str(exception.get("exception_message") or "")
    if "heterogeneous contract probe" not in message.casefold():
        return []
    return [
        {
            "reason": "provider_configuration_rejected",
            "exception": dict(exception),
        }
    ]


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
    pre_audit_channel: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from scripts.slurm import qasper_debug_contract as debug_contract

    extensions = debug_contract.qasper_debug_audit_extensions(
        [], contract_probe_predictions=predictions
    )
    metrics = dict(extensions.get("debug_gate_metrics") or {})
    hard_gates, coverage_failure = _hard_gates(metrics, predictions)
    provider_identity_violations = _provider_identity_failure(predictions)
    if not provider_identity_violations:
        provider_identity_violations = _provider_configuration_failure(failure_evidence)
    hard_gates[_PROVIDER_HETEROGENEITY_GATE] = {
        "value": 0.0 if provider_identity_violations else 1.0,
        "expected": 1.0,
        "passed": not provider_identity_violations,
    }
    _add_pre_audit_hard_gates(hard_gates, pre_audit_channel)
    failed_gates = [
        name for name, result in hard_gates.items() if result["passed"] is not True
    ]
    violations = debug_contract.qasper_debug_behavior_violations(
        [], contract_probe_predictions=predictions
    )
    lane_audit = dict(extensions.get("contract_probe_audit") or {})
    combined_failure_evidence = _probe_failure_evidence(
        failure_evidence=failure_evidence,
        coverage_failure=coverage_failure,
        provider_identity_violations=provider_identity_violations,
        pre_audit_channel=pre_audit_channel,
    )
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
        "provider_identity_violations": provider_identity_violations,
        "contract_probe_audit": lane_audit,
        "structural_state_matrix": extensions.get("structural_state_matrix") or {},
        "debug_gate_metrics": metrics,
        "failure_evidence": failure_details,
        "pre_audit_channel": pre_audit_channel or {},
    }


def _add_pre_audit_hard_gates(
    hard_gates: dict[str, dict[str, Any]],
    pre_audit_channel: dict[str, Any] | None,
) -> None:
    if pre_audit_channel is None:
        return
    values = {
        _PRE_AUDIT_COVERAGE_GATE: bool(pre_audit_channel.get("coverage_complete")),
        _PRE_AUDIT_TERMINAL_GATE: bool(
            pre_audit_channel.get("terminalization_complete")
        ),
    }
    for gate, passed in values.items():
        hard_gates[gate] = {
            "value": float(passed),
            "expected": 1.0,
            "passed": passed,
        }


def _probe_failure_evidence(
    *,
    failure_evidence: dict[str, Any] | None,
    coverage_failure: dict[str, str] | None,
    provider_identity_violations: list[dict[str, Any]],
    pre_audit_channel: dict[str, Any] | None,
) -> dict[str, Any]:
    evidence = dict(failure_evidence or {})
    if coverage_failure is not None:
        evidence["coverage_exception"] = coverage_failure
    if provider_identity_violations:
        evidence["provider_identity_violations"] = provider_identity_violations
    if pre_audit_channel is not None and pre_audit_channel.get("status") != "passed":
        evidence["pre_audit_channel"] = pre_audit_channel
    return evidence


def _pre_audit_channel_audit(
    rows: list[dict[str, Any]],
    *,
    source_path: Path,
    source_sha256: str,
) -> dict[str, Any]:
    expected = {case.case_id: case for case in NATURAL_QUALITY_PRE_AUDIT_CASES}
    observed: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []
    for row in rows:
        metadata = row.get("example_metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        case_data = metadata.get("contract_probe_case")
        case_data = case_data if isinstance(case_data, dict) else {}
        case_id = str(case_data.get("case_id") or "")
        if not case_id or case_id in observed:
            failures.append(
                {
                    "case_id": case_id,
                    "reason": "pre_audit_case_identity_invalid",
                }
            )
            continue
        observed[case_id] = row
    coverage_complete = bool(
        len(rows) == len(expected) and set(observed) == set(expected)
    )
    for case_id, case in expected.items():
        case_row = observed.get(case_id)
        if case_row is None:
            continue
        try:
            if case_row.get("qasper_debug_lane") != "contract_pre_audit":
                raise RuntimeError("pre-audit row is not in its independent lane")
            _assert_pre_audit_case(case, case_row)
        except RuntimeError as exc:
            failures.append({"case_id": case_id, "reason": str(exc)})
    terminalization_complete = bool(coverage_complete and not failures)
    return {
        "lane": "contract_pre_audit",
        "status": "passed" if terminalization_complete else "failed",
        "source": str(source_path.resolve()),
        "source_sha256": source_sha256,
        "prediction_count": len(rows),
        "expected_case_count": len(expected),
        "expected_case_ids": sorted(expected),
        "observed_case_ids": sorted(observed),
        "coverage_complete": coverage_complete,
        "terminalization_complete": terminalization_complete,
        "auditor_model_call_count": _auditor_model_call_count(rows),
        "failures": failures,
    }


def _auditor_model_call_count(rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        calls = row.get("contract_probe_live_calls")
        for call in calls if isinstance(calls, list) else []:
            if (
                isinstance(call, dict)
                and str(call.get("provider_role") or "").casefold() == "auditor"
            ):
                count += 1
    return count


def _audit_payload(
    predictions_path: Path,
    output_path: Path,
    predictions: list[dict[str, Any]],
    *,
    source_sha256: str,
    failure_evidence: dict[str, Any] | None,
    pre_audit_channel: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evaluated = _evaluate_probe(
        predictions,
        failure_evidence=failure_evidence,
        pre_audit_channel=pre_audit_channel,
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
    pre_audit_predictions_path: Path | None = None,
) -> dict[str, Any]:
    """Atomically publish fail-closed evidence without raising a hard gate."""

    predictions: list[dict[str, Any]] = []
    source_sha256: str | None = None
    pre_audit_channel: dict[str, Any] | None = None
    try:
        predictions = [
            row for row in read_jsonl(predictions_path) if isinstance(row, dict)
        ]
        source_sha256 = file_sha256(predictions_path)
        if pre_audit_predictions_path is not None:
            pre_audit_rows = [
                row
                for row in read_jsonl(pre_audit_predictions_path)
                if isinstance(row, dict)
            ]
            pre_audit_channel = _pre_audit_channel_audit(
                pre_audit_rows,
                source_path=pre_audit_predictions_path,
                source_sha256=file_sha256(pre_audit_predictions_path),
            )
        if evaluate_gates:
            audit = _audit_payload(
                predictions_path,
                output_path,
                predictions,
                source_sha256=source_sha256,
                failure_evidence=failure_evidence,
                pre_audit_channel=pre_audit_channel,
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
    pre_audit_predictions_path: Path | None = None,
) -> dict[str, Any]:
    predictions: list[dict[str, Any]] = []
    source_sha256: str | None = None
    pre_audit_channel: dict[str, Any] | None = None
    audit_written = False
    try:
        predictions = [
            row for row in read_jsonl(predictions_path) if isinstance(row, dict)
        ]
        source_sha256 = file_sha256(predictions_path)
        if pre_audit_predictions_path is not None:
            pre_audit_rows = [
                row
                for row in read_jsonl(pre_audit_predictions_path)
                if isinstance(row, dict)
            ]
            pre_audit_channel = _pre_audit_channel_audit(
                pre_audit_rows,
                source_path=pre_audit_predictions_path,
                source_sha256=file_sha256(pre_audit_predictions_path),
            )
        audit = _audit_payload(
            predictions_path,
            output_path,
            predictions,
            source_sha256=source_sha256,
            failure_evidence=failure_evidence,
            pre_audit_channel=pre_audit_channel,
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
    parser.add_argument("--pre-audit-predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        audit = validate_contract_probe(
            args.predictions.resolve(),
            output_path=args.output.resolve(),
            pre_audit_predictions_path=args.pre_audit_predictions.resolve(),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"contract_probe_status={audit['status']}")
    print(f"contract_probe_audit={args.output.resolve()}")


if __name__ == "__main__":
    main()
