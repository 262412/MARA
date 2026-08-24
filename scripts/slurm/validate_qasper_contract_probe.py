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


def validate_contract_probe(
    predictions_path: Path,
    *,
    output_path: Path,
) -> dict[str, Any]:
    predictions = [row for row in read_jsonl(predictions_path) if isinstance(row, dict)]
    extensions = qasper_debug_audit_extensions(
        [],
        contract_probe_predictions=predictions,
    )
    metrics = dict(extensions.get("debug_gate_metrics") or {})
    hard_gates = {
        name: {
            "value": metrics.get(name),
            "expected": expected,
            "passed": metrics.get(name) is not None
            and float(metrics[name]) == expected,
        }
        for name, expected in _HARD_GATES.items()
    }
    failed_gates = [
        name for name, result in hard_gates.items() if result["passed"] is not True
    ]
    violations = qasper_debug_behavior_violations(
        [],
        contract_probe_predictions=predictions,
    )
    lane_audit = dict(extensions.get("contract_probe_audit") or {})
    status = (
        "passed"
        if predictions
        and lane_audit.get("status") == "passed"
        and not violations
        and not failed_gates
        else "failed"
    )
    audit = {
        "contract": CONTRACT,
        "status": status,
        "source": str(predictions_path.resolve()),
        "source_sha256": file_sha256(predictions_path),
        "prediction_count": len(predictions),
        "replacement_candidate_allowed": False,
        "behavior_violations": violations,
        "hard_gates": hard_gates,
        "failed_gates": failed_gates,
        "contract_probe_audit": lane_audit,
        "structural_state_matrix": extensions.get("structural_state_matrix") or {},
        "debug_gate_metrics": metrics,
    }
    atomic_write_json(output_path, audit)
    if status != "passed":
        details = [*violations, *failed_gates]
        raise ValueError("provider contract probe failed: " + ",".join(details))
    return audit


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
