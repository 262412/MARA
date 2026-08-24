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
from benchmark.contract_invariant_metrics import (  # noqa: E402
    contract_invariant_summary,
)
from benchmark.jsonl import read_jsonl  # noqa: E402
from benchmark.terminal_outcome_contract import (  # noqa: E402
    terminal_outcome_summary_fields,
)
from scripts.slurm.contract_smoke_behavior import (  # noqa: E402
    finance_behavior_violations,
)
from scripts.slurm.qasper_debug_contract import (  # noqa: E402
    qasper_debug_audit_extensions,
    qasper_debug_behavior_violations,
    qasper_debug_contract_metrics,
)

CONTRACT = "contract_smoke_audit.v2"
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
HARD_GATES = {
    "identity_collision_count": ("eq", 0.0),
    "runtime_benchmark_roundtrip": ("eq", 1.0),
    "atomic_field_roundtrip_rate": ("eq", 1.0),
    "exact_atomic_identity_roundtrip": ("eq", 1.0),
    "exact_numeric_field_roundtrip": ("eq", 1.0),
    "normalized_label_roundtrip": ("eq", 1.0),
    "raw_representation_preservation": ("eq", 1.0),
    "reranker_lineage_violation_count": ("eq", 0.0),
    "citation_provenance_violation_count": ("eq", 0.0),
    "missing_execution_slot_answer_count": ("eq", 0.0),
    "required_slot_false_fill_count": ("eq", 0.0),
    "slot_semantic_false_fill_count": ("eq", 0.0),
    "slot_unresolved_reference_count": ("eq", 0.0),
    "plan_evidence_reference_resolution_rate": ("eq", 1.0),
    "source_page_cross_join_count": ("eq", 0.0),
    "calculation_render_mismatch_count": ("eq", 0.0),
    "heuristic_veto_after_verified_execution_count": ("eq", 0.0),
    "rounding_verification_failure_count": ("eq", 0.0),
    "qasper_stale_verifier_state_count": ("eq", 0.0),
    "gold_runtime_source_join_rate": ("eq", 1.0),
    "gold_source_schema_valid": ("eq", 1.0),
    "unresolved_gold_source_count": ("eq", 0.0),
    "ambiguous_source_alias_count": ("eq", 0.0),
    "gold_source_alias_resolution_rate": ("eq", 1.0),
    "gold_page_alias_resolution_rate": ("eq", 1.0),
    "gold_source_page_crosswalk_rate": ("eq", 1.0),
    "required_candidate_nonempty_rate": ("eq", 1.0),
    "required_selected_nonempty_rate": ("eq", 1.0),
    "required_generation_context_nonempty_rate": ("eq", 1.0),
    "citation_emission_coverage": ("eq", 1.0),
    "accepted_answer_citation_emission": ("eq", 1.0),
    "verified_claim_support_coverage": ("eq", 1.0),
    "final_answer_citation_emission": ("eq", 1.0),
    "terminal_outcome_contract_violation_count": ("eq", 0.0),
}
FINANCE_HARD_GATES = {
    "execution_slot_atomicity_rate": ("eq", 1.0),
    "execution_slot_materialization_rate": ("eq", 1.0),
    "execution_slot_binding_rate": ("eq", 1.0),
    "execution_operand_resolution_rate": ("eq", 1.0),
    "execution_slot_atomicity_violation_count": ("eq", 0.0),
    "parent_table_false_fill_count": ("eq", 0.0),
    "header_as_value_violation_count": ("eq", 0.0),
    "dimension_binding_rate": ("eq", 1.0),
    "dimension_scope_rate": ("eq", 1.0),
    "dimension_binding_violation_count": ("eq", 0.0),
    "dimension_scope_violation_count": ("eq", 0.0),
    "execution_operand_provenance_coverage": ("eq", 1.0),
    "reranker_execution_query_coverage": ("eq", 1.0),
    "reranker_unique_output_artifact_mismatch_count": ("eq", 0.0),
}
QASPER_HARD_GATES = {
    "abstention_candidate_sent_as_semantic_answer_count": ("eq", 0.0),
    "verifier_required_evidence_coverage": ("eq", 1.0),
    "qasper_required_slot_empty_state_count": ("eq", 0.0),
    "qasper_required_evidence_coverage_missing_count": ("eq", 0.0),
    "qasper_required_slot_authority_empty_count": ("eq", 0.0),
    "qasper_required_slot_authority_missing_count": ("eq", 0.0),
    "qasper_complete_to_unanswerable_empty_authority_count": ("eq", 0.0),
    "qasper_complete_to_unanswerable_identity_count": ("eq", 0.0),
    "qasper_complete_to_unanswerable_ref_mismatch_count": ("eq", 0.0),
    "qasper_semantic_veto_audit_violation_count": ("eq", 0.0),
    "contract_semantic_rewrite_count": ("eq", 0.0),
    "engine_scored_semantic_label_mismatch_count": ("eq", 0.0),
    "qasper_invalid_typed_label_count": ("eq", 0.0),
    "qasper_terminal_state_missing_count": ("eq", 0.0),
    "qasper_post_engine_answerability_llm_call_count": ("eq", 0.0),
    "qasper_runtime_authority_missing_count": ("eq", 0.0),
    "qasper_runtime_semantic_verifier_failure_count": ("eq", 0.0),
    "qasper_runtime_scope_failure_count": ("eq", 0.0),
    "qasper_composite_authority_invalid_count": ("eq", 0.0),
    "qasper_semantic_evidence_set_authority_invalid_count": ("eq", 0.0),
    "qasper_semantic_proposition_verifier_failure_count": ("eq", 0.0),
    "qasper_quote_validation_ref_mismatch_count": ("eq", 0.0),
    "answerable_false_abstention_count": ("eq", 0.0),
    "boolean_scope_violation_count": ("eq", 0.0),
    "wrong_polarity_count": ("eq", 0.0),
    "citation_claim_support_violation_count": ("eq", 0.0),
    "citation_scope_violation_count": ("eq", 0.0),
    "citation_nonminimal_count": ("eq", 0.0),
}
QASPER_DEBUG_HARD_GATES = {
    "terminal_outcome_contract_violation_count": ("eq", 0.0),
    "answerable_false_abstention_count": ("eq", 0.0),
    "qasper_quality_answerable_denominator_missing_count": ("eq", 0.0),
    "qasper_candidate_verifier_auditor_label_set_mismatch_count": ("eq", 0.0),
    "qasper_online_required_candidate_label_missing_count": ("eq", 0.0),
    "qasper_online_required_verifier_judgment_missing_count": ("eq", 0.0),
    "qasper_online_required_auditor_status_missing_count": ("eq", 0.0),
    "qasper_online_required_annotation_ambiguity_missing_count": ("eq", 0.0),
    "qasper_online_auditor_attempt_missing_count": ("eq", 0.0),
    "qasper_online_verifier_missing_count": ("eq", 0.0),
    "qasper_contract_probe_state_matrix_complete": ("eq", 1.0),
    "qasper_candidate_raw_identity_mismatch_count": ("eq", 0.0),
    "qasper_empty_candidate_audit_count": ("eq", 0.0),
    "qasper_empty_typed_conclusion_count": ("eq", 0.0),
    "qasper_semantic_entailment_audit_failure_count": ("eq", 0.0),
    "qasper_semantic_entailment_audit_rejection_count": ("eq", 0.0),
    "qasper_required_slot_unverified_count": ("eq", 0.0),
    "qasper_reverify_without_semantic_state_change_count": ("eq", 0.0),
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _load_predictions(path: Path) -> list[dict[str, Any]]:
    return [value for value in read_jsonl(path) if isinstance(value, dict)]


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
    answerable = any(
        str(answer or "").strip().lower()
        not in {
            "",
            "unanswerable",
            "insufficient evidence",
        }
        for answer in prediction.get("gold_answers") or []
    )
    for stage in STAGES:
        records = _records(metadata.get(stage))
        if stage in CORE_STAGES and answerable and stage in metadata and not records:
            status = "empty_required"
        elif stage in metadata:
            status = "recorded"
        elif stage == "reranked_evidence" and not (
            ranking_trace.get("executed")
            if "executed" in ranking_trace
            else ranking_trace.get("backend_execution")
        ):
            status = "truthfully_not_executed"
        elif stage == "execution_operand_evidence" and suite_kind in {
            "qasper",
            "qasper_debug",
        }:
            status = "not_applicable"
        elif stage == "execution_operand_evidence" and missing_execution:
            status = "blocked_missing_requirements"
        else:
            status = "missing"
        audit[stage] = {"status": status, "count": len(records)}
        if stage in CORE_STAGES and status in {"missing", "empty_required"}:
            missing.append(stage)
        if (
            stage == "reranked_evidence"
            and (
                ranking_trace.get("executed")
                if "executed" in ranking_trace
                else ranking_trace.get("backend_execution")
            )
            and status == "missing"
        ):
            missing.append(stage)
    if ranking_trace.get("executed") and int(
        ranking_trace.get("output_count") or 0
    ) != len(_records(metadata.get("reranked_evidence"))):
        missing.append("reranker_output_count_mismatch")
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


def _hard_gate_results(
    metrics: dict[str, Any],
    *,
    suite_kind: str,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    gates = (
        QASPER_DEBUG_HARD_GATES
        if suite_kind == "qasper_debug"
        else {
            **HARD_GATES,
            **(FINANCE_HARD_GATES if suite_kind == "finance" else {}),
            **(QASPER_HARD_GATES if suite_kind == "qasper" else {}),
        }
    )
    for metric, (comparison, expected) in gates.items():
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
        if missing:
            violations.append(
                {
                    "example_id": audit["example_id"],
                    "missing_stages": sorted(set(missing)),
                }
            )
    return audits, violations


def validate(run_dir: Path, *, suite_kind: str) -> dict[str, Any]:
    summary = _load_json(run_dir / "summary.json")
    predictions = _load_predictions(run_dir / "predictions.jsonl")
    expected_count = (18, 18) if suite_kind == "qasper_debug" else (2, 5)
    observed_requirements = _requirements(predictions)
    precondition_violations = _precondition_violations(
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
        )
        publish_contract_smoke_audit(run_dir, audit)
        raise ValueError("; ".join(precondition_violations))
    audit = _complete_audit(
        summary,
        predictions,
        suite_kind=suite_kind,
        expected_count=expected_count,
        observed_requirements=observed_requirements,
    )
    publish_contract_smoke_audit(run_dir, audit)
    if audit["status"] != "passed":
        raise ValueError("contract smoke failed: " + _failure_details(audit))
    return audit


def _complete_audit(
    summary: dict[str, Any],
    predictions: list[dict[str, Any]],
    *,
    suite_kind: str,
    expected_count: tuple[int, int],
    observed_requirements: set[str],
) -> dict[str, Any]:
    behavior_violations = _behavior_violations(
        predictions,
        suite_kind=suite_kind,
    )
    debug_extensions = (
        qasper_debug_audit_extensions(predictions)
        if suite_kind == "qasper_debug"
        else {"observability_coverage": {}, "structural_state_matrix": {}}
    )
    if (
        suite_kind == "qasper_debug"
        and debug_extensions["structural_state_matrix"].get("complete") is not True
    ):
        behavior_violations.append("structural_state_matrix_incomplete")
    stage_audits, stage_violations = _all_stage_audits(
        predictions, suite_kind=suite_kind
    )
    metrics = contract_invariant_summary(predictions)
    if suite_kind == "qasper_debug":
        metrics.update(qasper_debug_contract_metrics(predictions))
    hard_gates = _hard_gate_results(metrics, suite_kind=suite_kind)
    failed_gates = [
        metric for metric, result in hard_gates.items() if not result["passed"]
    ]
    contract_gate_failures = _contract_gate_failures(metrics, suite_kind=suite_kind)
    status = (
        "passed"
        if not stage_violations
        and not behavior_violations
        and not failed_gates
        and not contract_gate_failures
        else "failed"
    )
    audit = {
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
        **debug_extensions,
        "status": status,
    }
    return audit


def _precondition_violations(
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
    return violations


def _precondition_failure_audit(
    summary: dict[str, Any],
    predictions: list[dict[str, Any]],
    *,
    suite_kind: str,
    expected_count: tuple[int, int],
    observed_requirements: set[str],
    violations: list[str],
) -> dict[str, Any]:
    return {
        "contract": CONTRACT,
        "suite_kind": suite_kind,
        "artifact_detail": summary.get("artifact_detail"),
        "prediction_count": len(predictions),
        "expected_prediction_count": list(expected_count),
        "observed_requirements": sorted(observed_requirements),
        "precondition_violations": violations,
        **(
            qasper_debug_audit_extensions(predictions)
            if suite_kind == "qasper_debug"
            else {"observability_coverage": {}, "structural_state_matrix": {}}
        ),
        "status": "failed",
    }


def _contract_gate_failures(
    metrics: dict[str, Any],
    *,
    suite_kind: str,
) -> list[str]:
    if suite_kind == "qasper_debug":
        return []
    return [
        name
        for name, gate in dict(metrics.get("contract_gates") or {}).items()
        if isinstance(gate, dict) and gate.get("status") == "failed"
    ]


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
) -> list[str]:
    if suite_kind == "finance":
        return finance_behavior_violations(predictions)
    if suite_kind == "qasper_debug":
        return qasper_debug_behavior_violations(predictions)
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
    args = parser.parse_args()
    try:
        audit = validate(args.run_dir.resolve(), suite_kind=args.suite_kind)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"contract_smoke_status={audit['status']}")
    print(f"contract_smoke_audit={args.run_dir / 'contract_smoke_audit.json'}")


if __name__ == "__main__":
    main()
