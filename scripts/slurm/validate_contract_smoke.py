from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmark.contract_invariant_metrics import (  # noqa: E402
    contract_invariant_summary,
)

CONTRACT = "contract_smoke_audit.v1"
STAGES = (
    "canonical_candidate_evidence",
    "fused_evidence",
    "reranker_input_evidence",
    "reranked_evidence",
    "selected_evidence",
    "generation_context_evidence",
    "execution_operand_evidence",
    "verified_claim_support_evidence",
    "emitted_citation_evidence",
)
CORE_STAGES = {
    "canonical_candidate_evidence",
    "fused_evidence",
    "reranker_input_evidence",
    "selected_evidence",
    "generation_context_evidence",
    "verified_claim_support_evidence",
    "emitted_citation_evidence",
}
REQUIREMENTS = {
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
        "answerability_rewrite",
    },
}
HARD_GATES = {
    "identity_collision_count": ("eq", 0.0),
    "runtime_benchmark_roundtrip": ("eq", 1.0),
    "atomic_field_roundtrip_rate": ("eq", 1.0),
    "reranker_lineage_violation_count": ("eq", 0.0),
    "citation_provenance_violation_count": ("eq", 0.0),
    "missing_execution_slot_answer_count": ("eq", 0.0),
    "required_slot_false_fill_count": ("eq", 0.0),
    "source_page_cross_join_count": ("eq", 0.0),
    "calculation_render_mismatch_count": ("eq", 0.0),
    "qasper_stale_verifier_state_count": ("eq", 0.0),
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _load_predictions(path: Path) -> list[dict[str, Any]]:
    return [
        value
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for value in [json.loads(line)]
        if isinstance(value, dict)
    ]


def _records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _stage_audit(
    prediction: dict[str, Any],
    *,
    suite_kind: str,
) -> tuple[dict[str, Any], list[str]]:
    metadata = dict(prediction.get("evidence_metadata") or {})
    audit: dict[str, Any] = {"example_id": str(prediction.get("example_id") or "")}
    missing: list[str] = []
    ranking_trace = dict(metadata.get("ranking_trace") or {})
    query_plan = dict(metadata.get("query_plan") or {})
    slots = [
        dict(item)
        for item in query_plan.get("evidence_slots") or []
        if isinstance(item, dict)
    ]
    missing_execution = any(
        bool(slot.get("required_for_execution"))
        and str(slot.get("status") or "missing") != "filled"
        for slot in slots
    )
    for stage in STAGES:
        records = _records(metadata.get(stage))
        if stage in metadata:
            status = "recorded"
        elif stage == "reranked_evidence" and not ranking_trace.get(
            "backend_execution"
        ):
            status = "truthfully_not_executed"
        elif stage == "execution_operand_evidence" and suite_kind == "qasper":
            status = "not_applicable"
        elif stage == "execution_operand_evidence" and missing_execution:
            status = "blocked_missing_requirements"
        else:
            status = "missing"
        audit[stage] = {"status": status, "count": len(records)}
        if stage in CORE_STAGES and status == "missing":
            missing.append(stage)
        if (
            stage == "reranked_evidence"
            and ranking_trace.get("backend_execution")
            and status == "missing"
        ):
            missing.append(stage)
    return audit, missing


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


def _hard_gate_results(metrics: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for metric, (comparison, expected) in HARD_GATES.items():
        value = metrics.get(metric)
        passed = value is not None and (
            float(value) == expected if comparison == "eq" else False
        )
        results[metric] = {
            "value": value,
            "comparison": comparison,
            "expected": expected,
            "passed": passed,
        }
    return results


def _observed_qasper_answer_rewrite(prediction: dict[str, Any]) -> bool:
    pre = prediction.get("pre_contract_verification")
    post = prediction.get("post_contract_verification")
    metadata = dict(prediction.get("evidence_metadata") or {})
    trace = dict(metadata.get("qasper_answerability") or {})
    primary_answer = " ".join(
        str(trace.get("primary_answer") or "").strip().lower().split()
    )
    final_answer = " ".join(
        str(
            prediction.get("answer_for_scoring")
            or prediction.get("predicted_answer")
            or ""
        )
        .strip()
        .lower()
        .split()
    )
    return bool(
        isinstance(pre, dict)
        and isinstance(post, dict)
        and primary_answer
        and final_answer
        and primary_answer != final_answer
        and trace.get("citation_state") == "cleared_for_rebind"
        and metadata.get("answer_dependent_state") == "post_contract_verified"
    )


def validate(run_dir: Path, *, suite_kind: str) -> dict[str, Any]:
    summary = _load_json(run_dir / "summary.json")
    predictions = _load_predictions(run_dir / "predictions.jsonl")
    if summary.get("artifact_detail") != "full":
        raise ValueError("artifact_detail must be full for contract smoke")
    if not 2 <= len(predictions) <= 5:
        raise ValueError(
            "contract smoke must contain between 2 and 5 predictions; "
            f"found {len(predictions)}"
        )

    observed_requirements = _requirements(predictions)
    missing_requirements = REQUIREMENTS[suite_kind] - observed_requirements
    if missing_requirements:
        raise ValueError(
            "missing contract smoke requirements: "
            + ", ".join(sorted(missing_requirements))
        )
    behavior_violations: list[str] = []
    if suite_kind == "qasper" and not any(
        _observed_qasper_answer_rewrite(prediction) for prediction in predictions
    ):
        behavior_violations.append("answerability_rewrite_not_observed")

    stage_audits: list[dict[str, Any]] = []
    stage_violations: list[dict[str, Any]] = []
    for prediction in predictions:
        audit, missing = _stage_audit(prediction, suite_kind=suite_kind)
        stage_audits.append(audit)
        if missing:
            stage_violations.append(
                {
                    "example_id": audit["example_id"],
                    "missing_stages": sorted(set(missing)),
                }
            )

    metrics = contract_invariant_summary(predictions)
    hard_gates = _hard_gate_results(metrics)
    failed_gates = [
        metric for metric, result in hard_gates.items() if not result["passed"]
    ]
    status = (
        "passed"
        if not stage_violations and not behavior_violations and not failed_gates
        else "failed"
    )
    audit = {
        "contract": CONTRACT,
        "suite_kind": suite_kind,
        "artifact_detail": summary.get("artifact_detail"),
        "prediction_count": len(predictions),
        "observed_requirements": sorted(observed_requirements),
        "stage_audits": stage_audits,
        "stage_violations": stage_violations,
        "behavior_violations": behavior_violations,
        "hard_gates": hard_gates,
        "failed_gates": failed_gates,
        "status": status,
    }
    (run_dir / "contract_smoke_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if status != "passed":
        details = []
        if stage_violations:
            details.append(f"stage_violations={len(stage_violations)}")
        if behavior_violations:
            details.append("behavior_violations=" + ",".join(behavior_violations))
        if failed_gates:
            details.append("failed_gates=" + ",".join(failed_gates))
        raise ValueError("contract smoke failed: " + " ".join(details))
    return audit


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
    args = parser.parse_args()
    try:
        audit = validate(args.run_dir.resolve(), suite_kind=args.suite_kind)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"contract_smoke_status={audit['status']}")
    print(f"contract_smoke_audit={args.run_dir / 'contract_smoke_audit.json'}")


if __name__ == "__main__":
    main()
