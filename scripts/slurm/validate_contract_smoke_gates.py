from __future__ import annotations

from typing import Any

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
    "qasper_canonical_semantic_pack_mismatch_count": ("eq", 0.0),
    "qasper_quality_answerable_denominator_missing_count": ("eq", 0.0),
    "qasper_quality_annotation_ambiguity_missing_count": ("eq", 0.0),
}
QASPER_DEBUG_HARD_GATES = {
    "terminal_outcome_contract_violation_count": ("eq", 0.0),
    "answerable_false_abstention_count": ("eq", 0.0),
    "qasper_quality_answerable_denominator_missing_count": ("eq", 0.0),
    "qasper_quality_annotation_ambiguity_missing_count": ("eq", 0.0),
    "qasper_candidate_verifier_auditor_label_set_mismatch_count": ("eq", 0.0),
    "qasper_online_required_candidate_label_missing_count": ("eq", 0.0),
    "qasper_online_required_verifier_judgment_missing_count": ("eq", 0.0),
    "qasper_online_required_auditor_status_missing_count": ("eq", 0.0),
    "qasper_online_required_annotation_ambiguity_missing_count": ("eq", 0.0),
    "qasper_online_auditor_attempt_missing_count": ("eq", 0.0),
    "qasper_online_verifier_missing_count": ("eq", 0.0),
    "qasper_contract_probe_structural_state_matrix_complete": ("eq", 1.0),
    "qasper_contract_probe_required_online_states_complete": ("eq", 1.0),
    "qasper_candidate_raw_identity_mismatch_count": ("eq", 0.0),
    "qasper_controlled_candidate_transport_mismatch_count": ("eq", 0.0),
    "qasper_empty_candidate_audit_count": ("eq", 0.0),
    "qasper_empty_typed_conclusion_count": ("eq", 0.0),
    "qasper_semantic_entailment_audit_failure_count": ("eq", 0.0),
    "qasper_semantic_entailment_audit_rejection_count": ("eq", 0.0),
    "qasper_required_slot_unverified_count": ("eq", 0.0),
    "qasper_reverify_without_semantic_state_change_count": ("eq", 0.0),
    "qasper_canonical_semantic_pack_mismatch_count": ("eq", 0.0),
    "qasper_unexpected_unknown_assessment_count": ("eq", 0.0),
    "qasper_contract_probe_unexpected_false_abstention_count": ("eq", 0.0),
}
_QASPER_AMBIGUITY_COHORT_METRICS = {
    "answerable_false_abstention_count": (
        "qasper_all_rows_answerable_false_abstention_count"
    ),
    "verifier_required_evidence_coverage": (
        "qasper_all_rows_verifier_required_evidence_coverage"
    ),
    "qasper_required_slot_authority_empty_count": (
        "qasper_all_rows_required_slot_authority_empty_count"
    ),
    "qasper_required_slot_authority_missing_count": (
        "qasper_all_rows_required_slot_authority_missing_count"
    ),
}


def contract_smoke_gate_state(
    predictions: list[dict[str, Any]],
    *,
    suite_kind: str,
    contract_probe_predictions: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str], list[str]]:
    from benchmark.contract_invariant_metrics import contract_invariant_summary
    from scripts.slurm.qasper_debug_contract import qasper_debug_contract_metrics

    metrics = contract_invariant_summary(predictions)
    if suite_kind == "qasper_debug":
        metrics.update(
            qasper_debug_contract_metrics(
                predictions,
                contract_probe_predictions=contract_probe_predictions,
            )
        )
    elif suite_kind == "qasper":
        metrics = _qasper_full_gate_metrics(
            predictions,
            metrics,
            contract_invariant_summary=contract_invariant_summary,
            qasper_debug_contract_metrics=qasper_debug_contract_metrics,
        )
    hard_gates = hard_gate_results(metrics, suite_kind=suite_kind)
    failed_gates = [
        metric for metric, result in hard_gates.items() if not result["passed"]
    ]
    contract_gate_failures = (
        []
        if suite_kind == "qasper_debug"
        else [
            name
            for name, gate in dict(metrics.get("contract_gates") or {}).items()
            if isinstance(gate, dict) and gate.get("status") == "failed"
        ]
    )
    return metrics, hard_gates, failed_gates, contract_gate_failures


def _qasper_full_gate_metrics(
    predictions: list[dict[str, Any]],
    metrics: dict[str, Any],
    *,
    contract_invariant_summary: Any,
    qasper_debug_contract_metrics: Any,
) -> dict[str, Any]:
    qasper_metrics = qasper_debug_contract_metrics(predictions)
    unambiguous = [
        prediction
        for prediction in predictions
        if isinstance(prediction.get("qasper_annotation_diagnostics"), dict)
        and prediction["qasper_annotation_diagnostics"].get("ambiguous") is False
    ]
    cohort_metrics = contract_invariant_summary(unambiguous)
    for metric, all_rows_metric in _QASPER_AMBIGUITY_COHORT_METRICS.items():
        metrics[all_rows_metric] = metrics.get(metric)
        metrics[metric] = cohort_metrics.get(metric)
    for metric in (
        "answerable_false_abstention_count",
        "qasper_quality_answerable_denominator_missing_count",
        "qasper_quality_annotation_ambiguity_missing_count",
        "qasper_canonical_semantic_pack_mismatch_count",
    ):
        metrics[metric] = qasper_metrics[metric]
    return metrics


def hard_gate_results(
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
