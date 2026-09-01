from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmark.artifact_publication import publish_contract_smoke_audit  # noqa: E402
from benchmark.artifact_requirements import required_artifact_violations  # noqa: E402
from benchmark.jsonl import read_jsonl  # noqa: E402
from benchmark.terminal_outcome_contract import (  # noqa: E402
    terminal_outcome_summary_fields,
)
from scripts.slurm import validate_contract_smoke_gates as _gate_contract  # noqa: E402
from scripts.slurm import (  # noqa: E402
    validate_contract_smoke_stages as _stage_contract,
)
from scripts.slurm.contract_smoke_behavior import (  # noqa: E402
    finance_behavior_violations,
)
from scripts.slurm.qasper_causal_transaction_gate import (  # noqa: E402
    qasper_causal_transaction_artifact_audit,
)
from scripts.slurm.qasper_debug_contract import (  # noqa: E402
    qasper_debug_audit_extensions,
    qasper_debug_behavior_violations,
)
from scripts.slurm.validate_contract_smoke_gates import (  # noqa: E402
    contract_smoke_gate_state,
)
from scripts.slurm.validate_contract_smoke_probe import (  # noqa: E402
    contract_probe_preflight_audit as _contract_probe_preflight_audit,
)
from scripts.slurm.validate_contract_smoke_probe import (  # noqa: E402
    contract_probe_preflight_violations as _contract_probe_preflight_violations,
)
from benchmark.terminal_outcome_contract import (  # noqa: E402
    terminal_outcome_summary_fields,
)

CONTRACT = "contract_smoke_audit.v2"
HARD_GATES = _gate_contract.HARD_GATES
FINANCE_HARD_GATES = _gate_contract.FINANCE_HARD_GATES
QASPER_HARD_GATES = _gate_contract.QASPER_HARD_GATES
QASPER_DEBUG_HARD_GATES = _gate_contract.QASPER_DEBUG_HARD_GATES
STAGES = _stage_contract.STAGES
CORE_STAGES = _stage_contract.CORE_STAGES
_stage_audit = _stage_contract.stage_audit

REQUIREMENTS: dict[str, set[str]] = {
    "finance": {
        "same_parent_distinct_year_cells",
        "materialized_parent_operand",
        "header_or_caption_dimension",
        "multi_period_percentage_change",
        "missing_execution_requirement_abstains",
    },
    "qasper": {
        "ordinary_free_text",
        "yes_no",
        "support_and_contradiction",
        "cross_page_required_slots",
        "runtime_authority_pass_through",
    },
    "qasper_debug": set(),
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _load_predictions(path: Path) -> list[dict[str, Any]]:
    return [value for value in read_jsonl(path) if isinstance(value, dict)]


def _load_contract_probe_predictions(
    run_dir: Path,
    *,
    suite_kind: str,
    contract_probe_path: Path | None,
) -> list[dict[str, Any]]:
    if suite_kind != "qasper_debug":
        return []
    path = contract_probe_path or run_dir / "contract_probe_predictions.jsonl"
    if not path.is_file():
        return []
    return _load_predictions(path)


def _requirements(predictions: list[dict[str, Any]]) -> set[str]:
    values: set[str] = set()
    for prediction in predictions:
        metadata = dict(prediction.get("example_metadata") or {})
        values.update(
            str(value).strip()
            for value in metadata.get("contract_smoke_requirements") or []
            if str(value).strip()
        )
    return values


def _observed_qasper_runtime_pass_through(prediction: dict[str, Any]) -> bool:
    metadata = prediction.get("evidence_metadata")
    trace = metadata.get("qasper_answerability") if isinstance(metadata, dict) else None
    trace = trace if isinstance(trace, dict) else {}
    terminal_state = prediction.get("engine_terminal_state")
    return bool(
        str(prediction.get("answer_type") or "").lower() == "boolean"
        and trace.get("runtime_projection_present") is True
        and isinstance(terminal_state, dict)
        and terminal_state.get("contract_id") == "engine_terminal_state.v1"
        and str(prediction.get("engine_terminal_projection_hash") or "")
        and str(trace.get("contract_action") or "") == "pass_through"
        and trace.get("contract_semantic_rewrite") is False
        and int(trace.get("post_engine_answerability_llm_call_count") or 0) == 0
    )


def _all_stage_audits(
    predictions: list[dict[str, Any]],
    *,
    suite_kind: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    audits: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    for prediction in predictions:
        audit, missing = _stage_audit(prediction, suite_kind=suite_kind)
        audits.append(audit)
        fusion_violations = list(audit.get("fusion_stage", {}).get("violations") or [])
        if missing or fusion_violations:
            violations.append(
                {
                    "example_id": audit["example_id"],
                    "missing_stages": sorted(set(missing)),
                    **(
                        {"fusion_stage_violations": fusion_violations}
                        if fusion_violations
                        else {}
                    ),
                }
            )
    return audits, violations


def validate(
    run_dir: Path,
    *,
    suite_kind: str,
    contract_probe_path: Path | None = None,
    retrieval_index_artifact_path: Path | None = None,
    retrieval_index_restore_audit_path: Path | None = None,
) -> dict[str, Any]:
    summary = _load_json(run_dir / "summary.json")
    predictions = _load_predictions(run_dir / "predictions.jsonl")
    contract_probe_predictions = _load_contract_probe_predictions(
        run_dir,
        suite_kind=suite_kind,
        contract_probe_path=contract_probe_path,
    )
    expected_count = (18, 18) if suite_kind == "qasper_debug" else (2, 5)
    observed_requirements = _requirements(predictions)
    if suite_kind == "qasper_debug":
        retrieval_index_artifact_path = (
            retrieval_index_artifact_path
            or run_dir / "retrieval_index_artifact.json"
        )
        retrieval_index_restore_audit_path = (
            retrieval_index_restore_audit_path
            or run_dir / "retrieval_index_restore_audit.json"
        )
    precondition_violations = _precondition_violations(
        run_dir,
        summary,
        predictions,
        suite_kind=suite_kind,
        expected_count=expected_count,
        observed_requirements=observed_requirements,
    )
    if precondition_violations:
        audit = _precondition_failure_audit(
            summary,
            predictions,
            suite_kind=suite_kind,
            expected_count=expected_count,
            observed_requirements=observed_requirements,
            violations=precondition_violations,
            contract_probe_predictions=contract_probe_predictions,
        )
        publish_contract_smoke_audit(run_dir, audit)
        raise ValueError("; ".join(precondition_violations))
    audit = _complete_audit(
        run_dir,
        summary,
        predictions,
        suite_kind=suite_kind,
        expected_count=expected_count,
        observed_requirements=observed_requirements,
        contract_probe_predictions=contract_probe_predictions,
        retrieval_index_artifact_path=retrieval_index_artifact_path,
        retrieval_index_restore_audit_path=retrieval_index_restore_audit_path,
    )
    publish_contract_smoke_audit(run_dir, audit)
    if audit["status"] != "passed":
        raise ValueError("contract smoke failed: " + _failure_details(audit))
    return audit


def _complete_audit(
    run_dir: Path,
    summary: dict[str, Any],
    predictions: list[dict[str, Any]],
    *,
    suite_kind: str,
    expected_count: tuple[int, int],
    observed_requirements: set[str],
    contract_probe_predictions: list[dict[str, Any]],
    retrieval_index_artifact_path: Path | None,
    retrieval_index_restore_audit_path: Path | None,
) -> dict[str, Any]:
    (
        causal_transaction_audit,
        causal_transaction_violations,
    ) = _causal_transaction_audit(
        run_dir,
        summary,
        predictions,
        suite_kind=suite_kind,
        retrieval_index_artifact_path=retrieval_index_artifact_path,
        retrieval_index_restore_audit_path=retrieval_index_restore_audit_path,
    )
    behavior_violations = _behavior_violations(
        predictions,
        suite_kind=suite_kind,
        contract_probe_predictions=contract_probe_predictions,
    )
    behavior_violations.extend(causal_transaction_violations)
    behavior_violations.extend(
        _contract_probe_preflight_violations(
            run_dir,
            suite_kind=suite_kind,
            prediction_count=len(contract_probe_predictions),
        )
    )
    debug_extensions, debug_violations = _debug_extensions(
        predictions,
        suite_kind=suite_kind,
        contract_probe_predictions=contract_probe_predictions,
    )
    behavior_violations.extend(debug_violations)
    stage_audits, stage_violations = _all_stage_audits(
        predictions, suite_kind=suite_kind
    )
    (
        metrics,
        hard_gates,
        failed_gates,
        contract_gate_failures,
    ) = contract_smoke_gate_state(
        predictions,
        suite_kind=suite_kind,
        contract_probe_predictions=contract_probe_predictions,
    )
    status = _audit_status(
        stage_violations,
        behavior_violations,
        failed_gates,
        contract_gate_failures,
    )
    return _complete_audit_payload(
        run_dir,
        summary,
        predictions,
        suite_kind=suite_kind,
        expected_count=expected_count,
        observed_requirements=observed_requirements,
        stage_audits=stage_audits,
        stage_violations=stage_violations,
        behavior_violations=behavior_violations,
        metrics=metrics,
        hard_gates=hard_gates,
        failed_gates=failed_gates,
        contract_gate_failures=contract_gate_failures,
        causal_transaction_audit=causal_transaction_audit,
        debug_extensions=debug_extensions,
        status=status,
    )


def _complete_audit_payload(
    run_dir: Path,
    summary: dict[str, Any],
    predictions: list[dict[str, Any]],
    *,
    suite_kind: str,
    expected_count: tuple[int, int],
    observed_requirements: set[str],
    stage_audits: list[dict[str, Any]],
    stage_violations: list[dict[str, Any]],
    behavior_violations: list[str],
    metrics: dict[str, Any],
    hard_gates: dict[str, Any],
    failed_gates: list[str],
    contract_gate_failures: list[str],
    causal_transaction_audit: dict[str, Any],
    debug_extensions: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    return {
        "contract": CONTRACT,
        "suite_kind": suite_kind,
        "artifact_detail": summary.get("artifact_detail"),
        "prediction_count": len(predictions),
        "expected_prediction_count": list(expected_count),
        "observed_requirements": sorted(observed_requirements),
        "stage_audits": stage_audits,
        "stage_violations": stage_violations,
        "behavior_violations": behavior_violations,
        "hard_gates": hard_gates,
        "failed_gates": failed_gates,
        "contract_gates": metrics.get("contract_gates"),
        "contract_gate_failures": contract_gate_failures,
        "terminal_outcome_summary": terminal_outcome_summary_fields(predictions),
        "provider_contract_probe_audit": _contract_probe_preflight_audit(
            run_dir,
            suite_kind=suite_kind,
        ),
        "causal_transaction_audit": causal_transaction_audit,
        **debug_extensions,
        "status": status,
    }


def _causal_transaction_audit(
    run_dir: Path,
    summary: dict[str, Any],
    predictions: list[dict[str, Any]],
    *,
    suite_kind: str,
    retrieval_index_artifact_path: Path | None,
    retrieval_index_restore_audit_path: Path | None,
) -> tuple[dict[str, Any], list[str]]:
    provenance = summary.get("run_provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    git = provenance.get("git")
    git = git if isinstance(git, dict) else {}
    return qasper_causal_transaction_artifact_audit(
        run_dir,
        predictions,
        suite_kind=suite_kind,
        retrieval_index_artifact_path=retrieval_index_artifact_path,
        retrieval_index_restore_audit_path=retrieval_index_restore_audit_path,
        expected_code_sha=str(git.get("commit") or ""),
        expected_index_contract=str(provenance.get("index_contract") or ""),
        expected_embedding_contract=str(
            provenance.get("embedding_contract") or ""
        ),
        require_retrieval_index_binding=True,
    )


def _audit_status(*violation_groups: Any) -> str:
    return "failed" if any(violation_groups) else "passed"


def _debug_extensions(
    predictions: list[dict[str, Any]],
    *,
    suite_kind: str,
    contract_probe_predictions: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    if suite_kind != "qasper_debug":
        return {"observability_coverage": {}, "structural_state_matrix": {}}, []
    extensions = qasper_debug_audit_extensions(
        predictions,
        contract_probe_predictions=contract_probe_predictions,
    )
    violations = []
    if extensions["structural_state_matrix"].get("complete") is not True:
        violations.append("structural_state_matrix_incomplete")
    return extensions, violations


def _precondition_violations(
    run_dir: Path,
    summary: dict[str, Any],
    predictions: list[dict[str, Any]],
    *,
    suite_kind: str,
    expected_count: tuple[int, int],
    observed_requirements: set[str],
) -> list[str]:
    violations: list[str] = []
    if summary.get("artifact_detail") != "full":
        violations.append("artifact_detail must be full for contract smoke")
    if not expected_count[0] <= len(predictions) <= expected_count[1]:
        violations.append(
            "contract smoke must contain between "
            f"{expected_count[0]} and {expected_count[1]} predictions; "
            f"found {len(predictions)}"
        )
    missing_requirements = REQUIREMENTS[suite_kind] - observed_requirements
    if missing_requirements:
        violations.append(
            "missing contract smoke requirements: "
            + ", ".join(sorted(missing_requirements))
        )
    violations.extend(required_artifact_violations(run_dir, predictions))
    return violations


def _precondition_failure_audit(
    summary: dict[str, Any],
    predictions: list[dict[str, Any]],
    *,
    suite_kind: str,
    expected_count: tuple[int, int],
    observed_requirements: set[str],
    violations: list[str],
    contract_probe_predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "contract": CONTRACT,
        "suite_kind": suite_kind,
        "artifact_detail": summary.get("artifact_detail"),
        "prediction_count": len(predictions),
        "expected_prediction_count": list(expected_count),
        "observed_requirements": sorted(observed_requirements),
        "precondition_violations": violations,
        "stage_audits": [],
        "stage_violations": [],
        "behavior_violations": [],
        "hard_gates": {},
        "failed_gates": ["preconditions"],
        "contract_gates": {},
        "contract_gate_failures": [],
        "causal_transaction_audit": {
            "contract_id": "qasper_causal_transaction_artifact_audit.v1",
            "applicable": suite_kind == "qasper_debug",
            "status": "not_evaluated",
            "hard_rule": "stop_at_first_divergence",
            "observations": [],
            "violations": [],
        },
        **(
            qasper_debug_audit_extensions(
                predictions,
                contract_probe_predictions=contract_probe_predictions,
            )
            if suite_kind == "qasper_debug"
            else {"observability_coverage": {}, "structural_state_matrix": {}}
        ),
        "status": "failed",
    }


def _failure_details(audit: dict[str, Any]) -> str:
    details: list[str] = []
    if audit["stage_violations"]:
        details.append(f"stage_violations={len(audit['stage_violations'])}")
    if audit["behavior_violations"]:
        details.append("behavior_violations=" + ",".join(audit["behavior_violations"]))
    if audit["failed_gates"]:
        details.append("failed_gates=" + ",".join(audit["failed_gates"]))
    if audit["contract_gate_failures"]:
        details.append(
            "contract_gate_failures=" + ",".join(audit["contract_gate_failures"])
        )
    return " ".join(details)


def _behavior_violations(
    predictions: list[dict[str, Any]],
    *,
    suite_kind: str,
    contract_probe_predictions: list[dict[str, Any]] | None = None,
) -> list[str]:
    if suite_kind == "finance":
        return finance_behavior_violations(predictions)
    if suite_kind == "qasper_debug":
        return qasper_debug_behavior_violations(
            predictions,
            contract_probe_predictions=contract_probe_predictions,
        )
    violations: list[str] = []
    if not any(
        _observed_qasper_runtime_pass_through(prediction) for prediction in predictions
    ):
        violations.append("runtime_authority_pass_through_not_observed")
    required_trace_fields = (
        "engine_terminal_answer",
        "engine_semantic_label",
        "scored_semantic_label",
        "contract_semantic_rewrite",
        "runtime_projection_present",
        "runtime_boolean_authority_applicable",
        "runtime_authority_failure_kind",
        "post_engine_answerability_llm_call_count",
    )
    for prediction in predictions:
        trace = dict(
            dict(prediction.get("evidence_metadata") or {}).get("qasper_answerability")
            or {}
        )
        if trace.get("status") == "ok" and any(
            field not in trace for field in required_trace_fields
        ):
            violations.append(
                f"verifier_input_trace_missing:{prediction.get('example_id')}"
            )
    return violations


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a full-detail FinanceBench or QASPER contract smoke."
    )
    parser.add_argument("run_dir", type=Path)
    parser.add_argument(
        "--suite-kind",
        choices=tuple(sorted(REQUIREMENTS)),
        required=True,
    )
    parser.add_argument(
        "--retrieval-index-artifact",
        type=Path,
        help=(
            "Frozen real QASPER Stage 2 artifact required by formal debug runs."
        ),
    )
    parser.add_argument(
        "--retrieval-index-restore-audit",
        type=Path,
        help="Job-owned proof that the frozen QASPER index tree was restored.",
    )
    parser.add_argument(
        "--contract-probe-predictions",
        type=Path,
        help=(
            "Separate live QASPER contract-probe JSONL artifact. "
            "Required for qasper_debug validation."
        ),
    )
    args = parser.parse_args()
    try:
        audit = validate(
            args.run_dir.resolve(),
            suite_kind=args.suite_kind,
            contract_probe_path=(
                args.contract_probe_predictions.resolve()
                if args.contract_probe_predictions
                else None
            ),
            retrieval_index_artifact_path=(
                args.retrieval_index_artifact.resolve()
                if args.retrieval_index_artifact
                else None
            ),
            retrieval_index_restore_audit_path=(
                args.retrieval_index_restore_audit.resolve()
                if args.retrieval_index_restore_audit
                else None
            ),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"contract_smoke_status={audit['status']}")
    print(f"contract_smoke_audit={args.run_dir / 'contract_smoke_audit.json'}")


if __name__ == "__main__":
    main()
