from __future__ import annotations

from typing import Any

from .contract_gate_metrics import contract_gate_summary
from .metrics import safe_mean


def summarize_contract_invariants(
    metrics: list[dict[str, float | None]],
) -> dict[str, Any]:
    summary = {
        **_identity_summary(metrics),
        **_execution_summary(metrics),
        **_source_summary(metrics),
    }
    summary.update(contract_gate_summary(metrics))
    return summary


def _identity_summary(
    metrics: list[dict[str, float | None]],
) -> dict[str, float | None]:
    return {
        "gold_source_alias_resolution_rate": _mean(
            metrics,
            "gold_source_alias_resolution_rate",
        ),
        "gold_page_alias_resolution_rate": _mean(
            metrics,
            "gold_page_alias_resolution_rate",
        ),
        "gold_source_page_crosswalk_rate": _mean(
            metrics,
            "gold_source_page_crosswalk_rate",
        ),
        "retrieved_gold_source_page_coverage": _mean(
            metrics,
            "retrieved_gold_source_page_coverage",
        ),
        "duplicate_identity_count": _sum(metrics, "duplicate_identity_count"),
        "conflicting_identity_count": _sum(metrics, "conflicting_identity_count"),
        "canonical_id_mismatch_count": _sum(
            metrics,
            "canonical_id_mismatch_count",
        ),
        "atomic_field_roundtrip_rate": _mean(
            metrics,
            "atomic_field_roundtrip_rate",
        ),
        "exact_atomic_identity_roundtrip": _mean(
            metrics,
            "exact_atomic_identity_roundtrip",
        ),
        "exact_numeric_field_roundtrip": _mean(
            metrics,
            "exact_numeric_field_roundtrip",
        ),
        "normalized_label_roundtrip": _mean(
            metrics,
            "normalized_label_roundtrip",
        ),
        "raw_representation_preservation": _mean(
            metrics,
            "raw_representation_preservation",
        ),
        "normalization_equivalence_count": _sum(
            metrics,
            "normalization_equivalence_count",
        ),
        "locator_roundtrip_rate": _mean(metrics, "locator_roundtrip_rate"),
        "lineage_roundtrip_rate": _mean(metrics, "lineage_roundtrip_rate"),
        "representation_roundtrip_rate": _mean(
            metrics,
            "representation_roundtrip_rate",
        ),
        "identity_collision_count": _sum(metrics, "identity_collision_count"),
        "runtime_benchmark_roundtrip": _mean(
            metrics,
            "runtime_benchmark_roundtrip",
        ),
        "citation_provenance_violation_count": _sum(
            metrics,
            "citation_provenance_violation_count",
        ),
        "reranker_lineage_violation_count": _sum(
            metrics,
            "reranker_lineage_violation_count",
        ),
    }


def _execution_summary(
    metrics: list[dict[str, float | None]],
) -> dict[str, float | None]:
    return {
        **_execution_binding_summary(metrics),
        **_dimension_binding_summary(metrics),
        **_verification_summary(metrics),
    }


def _execution_binding_summary(
    metrics: list[dict[str, float | None]],
) -> dict[str, float | None]:
    return {
        "missing_execution_slot_answer_count": _sum(
            metrics,
            "missing_execution_slot_answer_count",
        ),
        "required_slot_false_fill_count": _sum(
            metrics,
            "required_slot_false_fill_count",
        ),
        "slot_semantic_false_fill_count": _sum(
            metrics,
            "slot_semantic_false_fill_count",
        ),
        "slot_unresolved_reference_count": _sum(
            metrics,
            "slot_unresolved_reference_count",
        ),
        "plan_evidence_reference_resolution_rate": _mean(
            metrics,
            "plan_evidence_reference_resolution_rate",
        ),
        "execution_slot_atomicity_rate": _mean(
            metrics,
            "execution_slot_atomicity_rate",
        ),
        "execution_slot_materialization_rate": _mean(
            metrics,
            "execution_slot_materialization_rate",
        ),
        "execution_slot_binding_rate": _mean(
            metrics,
            "execution_slot_binding_rate",
        ),
        "execution_operand_resolution_rate": _mean(
            metrics,
            "execution_operand_resolution_rate",
        ),
        "execution_slot_atomicity_violation_count": _sum(
            metrics,
            "execution_slot_atomicity_violation_count",
        ),
        "parent_table_false_fill_count": _sum(
            metrics,
            "parent_table_false_fill_count",
        ),
        "header_as_value_violation_count": _sum(
            metrics,
            "header_as_value_violation_count",
        ),
        "source_page_cross_join_count": _sum(
            metrics,
            "source_page_cross_join_count",
        ),
        "calculation_render_mismatch_count": _sum(
            metrics,
            "calculation_render_mismatch_count",
        ),
        "heuristic_veto_after_verified_execution_count": _sum(
            metrics,
            "heuristic_veto_after_verified_execution_count",
        ),
        "rounding_verification_failure_count": _sum(
            metrics,
            "rounding_verification_failure_count",
        ),
        "query_plan_calculation_plan_state_mismatch_count": _sum(
            metrics,
            "query_plan_calculation_plan_state_mismatch_count",
        ),
        "verified_execution_gold_discrepancy_count": _sum(
            metrics,
            "verified_execution_gold_discrepancy_count",
        ),
    }


def _dimension_binding_summary(
    metrics: list[dict[str, float | None]],
) -> dict[str, float | None]:
    return {
        "execution_operand_slot_count": _sum(
            metrics,
            "execution_operand_slot_count",
        ),
        "execution_dimension_slot_count": _sum(
            metrics,
            "execution_dimension_slot_count",
        ),
        "execution_other_slot_count": _sum(
            metrics,
            "execution_other_slot_count",
        ),
        "dimension_binding_rate": _mean(metrics, "dimension_binding_rate"),
        "dimension_scope_rate": _mean(metrics, "dimension_scope_rate"),
        "effective_scale_coverage_rate": _mean(
            metrics,
            "effective_scale_coverage_rate",
        ),
        "effective_scale_missing_count": _sum(
            metrics,
            "effective_scale_missing_count",
        ),
        "dimension_binding_violation_count": _sum(
            metrics,
            "dimension_binding_violation_count",
        ),
        "dimension_scope_violation_count": _sum(
            metrics,
            "dimension_scope_violation_count",
        ),
    }


def _verification_summary(
    metrics: list[dict[str, float | None]],
) -> dict[str, float | None]:
    return {
        **_required_verification_summary(metrics),
        "qasper_stale_verifier_state_count": _sum(
            metrics,
            "qasper_stale_verifier_state_count",
        ),
        "stored_recomputed_qasper_evidence_f1_mismatch_count": _sum(
            metrics,
            "stored_recomputed_qasper_evidence_f1_mismatch_count",
        ),
        "abstention_candidate_sent_as_semantic_answer_count": _sum(
            metrics,
            "abstention_candidate_sent_as_semantic_answer_count",
        ),
        "verifier_required_evidence_coverage": _mean(
            metrics,
            "verifier_required_evidence_coverage",
        ),
        "answerable_false_abstention_count": _sum(
            metrics,
            "answerable_false_abstention_count",
        ),
        "boolean_scope_violation_count": _sum(
            metrics,
            "boolean_scope_violation_count",
        ),
        "wrong_polarity_count": _sum(metrics, "wrong_polarity_count"),
        "qasper_required_slot_authority_empty_count": _sum(
            metrics,
            "qasper_required_slot_authority_empty_count",
        ),
        "qasper_required_slot_authority_missing_count": _sum(
            metrics,
            "qasper_required_slot_authority_missing_count",
        ),
        "qasper_complete_to_unanswerable_empty_authority_count": _sum(
            metrics,
            "qasper_complete_to_unanswerable_empty_authority_count",
        ),
        "qasper_complete_to_unanswerable_identity_count": _sum(
            metrics,
            "qasper_complete_to_unanswerable_identity_count",
        ),
        "qasper_complete_to_unanswerable_ref_mismatch_count": _sum(
            metrics,
            "qasper_complete_to_unanswerable_ref_mismatch_count",
        ),
        "qasper_semantic_veto_audit_violation_count": _sum(
            metrics,
            "qasper_semantic_veto_audit_violation_count",
        ),
        "citation_claim_support_violation_count": _sum(
            metrics,
            "citation_claim_support_violation_count",
        ),
        "citation_scope_violation_count": _sum(
            metrics,
            "citation_scope_violation_count",
        ),
        "citation_nonminimal_count": _sum(
            metrics,
            "citation_nonminimal_count",
        ),
    }


def _required_verification_summary(
    metrics: list[dict[str, float | None]],
) -> dict[str, float]:
    keys = (
        "qasper_required_verification_applicable_count",
        "qasper_required_slot_nonempty_state_count",
        "qasper_required_slot_empty_state_count",
        "qasper_required_evidence_coverage_missing_count",
    )
    return {key: _sum(metrics, key) for key in keys}


def _source_summary(
    metrics: list[dict[str, float | None]],
) -> dict[str, float | None]:
    return {
        "gold_runtime_source_join_rate": _mean(
            metrics,
            "gold_runtime_source_join_rate",
        ),
        "unresolved_gold_source_count": _sum(
            metrics,
            "unresolved_gold_source_count",
        ),
        "ambiguous_source_alias_count": _sum(
            metrics,
            "ambiguous_source_alias_count",
        ),
        "gold_runtime_source_page_join_rate": _mean(
            metrics,
            "gold_runtime_source_page_join_rate",
        ),
        "gold_source_schema_valid": _mean(metrics, "gold_source_schema_valid"),
        "gold_source_id_count": _sum(metrics, "gold_source_id_count"),
        "gold_evidence_text_support_recall": _mean(
            metrics,
            "gold_evidence_text_support_recall",
        ),
    }


def _sum(metrics: list[dict[str, float | None]], key: str) -> float:
    return sum(float(metric.get(key) or 0.0) for metric in metrics)


def _mean(
    metrics: list[dict[str, float | None]],
    key: str,
) -> float | None:
    return safe_mean(
        [value for metric in metrics if (value := metric.get(key)) is not None]
    )
