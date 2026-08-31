from __future__ import annotations

from typing import Any


def metric_payload(
    counts: dict[str, int],
    flags: dict[str, bool],
    *,
    quality_flags: dict[str, bool],
    probe_flags: dict[str, bool],
    quality_counts: dict[str, int],
    probe_counts: dict[str, int],
    quality_count: int,
    probe_count: int,
    probe_observation: dict[str, Any],
    structural_matrix_complete: bool,
) -> dict[str, float]:
    required_slot_unverified = (
        quality_counts["unambiguous_supported_slot_unverified"]
        + quality_counts["unambiguous_answerable_slot_unverified"]
        - quality_counts["unambiguous_required_slot_overlap"]
    )
    expected_ambiguity_required_slot_unverified = (
        quality_counts["expected_ambiguity_supported_slot_unverified"]
        + quality_counts["expected_ambiguity_answerable_slot_unverified"]
        - quality_counts["expected_ambiguity_required_slot_overlap"]
    )
    required_probe_states_complete = bool(
        probe_count
        and not probe_flags["label_mismatch"]
        and not probe_flags["missing_candidate_labels"]
        and not probe_flags["missing_verifier_judgments"]
        and not probe_flags["missing_auditor_statuses"]
    )
    return {
        **_summary_metrics(
            counts,
            quality_count=quality_count,
            probe_count=probe_count,
            probe_observation=probe_observation,
            structural_matrix_complete=structural_matrix_complete,
            required_slot_unverified=required_slot_unverified,
            expected_ambiguity_required_slot_unverified=(
                expected_ambiguity_required_slot_unverified
            ),
            required_probe_states_complete=required_probe_states_complete,
            quality_counts=quality_counts,
        ),
        **_online_metrics(counts, flags),
        **_lane_metrics(
            quality_flags,
            probe_flags,
            quality_counts=quality_counts,
            probe_counts=probe_counts,
        ),
    }


def _summary_metrics(
    counts: dict[str, int],
    *,
    quality_count: int,
    probe_count: int,
    probe_observation: dict[str, Any],
    structural_matrix_complete: bool,
    required_slot_unverified: int,
    expected_ambiguity_required_slot_unverified: int,
    required_probe_states_complete: bool,
    quality_counts: dict[str, int],
) -> dict[str, float]:
    return {
        "answerable_false_abstention_count": float(
            quality_counts["unambiguous_false_abstentions"]
        ),
        "qasper_quality_prediction_count": float(quality_count),
        "qasper_contract_probe_prediction_count": float(probe_count),
        "qasper_quality_answerable_row_count": float(counts["answerable_rows"]),
        "qasper_quality_answerable_required_slot_unverified_count": float(
            quality_counts["unambiguous_answerable_slot_unverified"]
        ),
        **_quality_cohort_metrics(
            quality_counts,
            expected_ambiguity_required_slot_unverified,
        ),
        "qasper_quality_answerable_denominator_missing_count": float(
            counts["answerable_rows"] == 0
        ),
        "qasper_contract_probe_observed_state_cell_count": float(
            probe_observation.get("observed_state_cell_count", 0)
        ),
        "qasper_contract_probe_state_matrix_complete": float(
            bool(probe_observation.get("state_matrix_complete", False))
        ),
        "qasper_contract_probe_structural_state_matrix_complete": float(
            structural_matrix_complete
        ),
        "qasper_contract_probe_live_state_matrix_complete": float(
            bool(probe_observation.get("state_matrix_complete", False))
        ),
        "qasper_contract_probe_required_online_states_complete": float(
            required_probe_states_complete
        ),
        "qasper_supported_row_required_slot_unverified_count": float(
            counts["supported_slot_unverified"]
        ),
        "qasper_candidate_raw_identity_mismatch_count": float(
            counts["raw_identity_mismatches"]
        ),
        "qasper_controlled_candidate_transport_mismatch_count": float(
            counts["controlled_transport_mismatches"]
        ),
        "qasper_empty_candidate_audit_count": float(counts["empty_audits"]),
        "qasper_empty_typed_conclusion_count": float(counts["empty_typed_conclusions"]),
        "qasper_semantic_entailment_audit_failure_count": float(
            counts["entailment_failures"]
        ),
        "qasper_semantic_entailment_audit_rejection_count": float(
            counts["entailment_rejections"]
        ),
        "qasper_required_slot_unverified_count": float(required_slot_unverified),
        "qasper_reverify_without_semantic_state_change_count": float(
            counts["reverify_without_state_change"]
        ),
        "qasper_canonical_semantic_pack_mismatch_count": float(
            counts["canonical_pack_mismatches"]
        ),
    }


def _quality_cohort_metrics(
    quality_counts: dict[str, int],
    expected_ambiguity_required_slot_unverified: int,
) -> dict[str, float]:
    return {
        "qasper_quality_expected_ambiguity_unresolved_count": float(
            quality_counts["expected_ambiguity_unresolved"]
        ),
        "qasper_quality_expected_ambiguity_row_count": float(
            quality_counts["expected_ambiguity_rows"]
        ),
        "qasper_quality_unambiguous_false_abstention_count": float(
            quality_counts["unambiguous_false_abstentions"]
        ),
        "qasper_quality_unambiguous_answerable_row_count": float(
            quality_counts["unambiguous_answerable_rows"]
        ),
        "qasper_quality_expected_ambiguity_required_slot_unverified_count": float(
            expected_ambiguity_required_slot_unverified
        ),
        "qasper_quality_unambiguous_answerable_required_slot_unverified_count": float(
            quality_counts["unambiguous_answerable_slot_unverified"]
        ),
    }


def _online_metrics(
    counts: dict[str, int],
    flags: dict[str, bool],
) -> dict[str, float]:
    return {
        "qasper_candidate_verifier_auditor_label_set_mismatch_count": float(
            flags["label_mismatch"]
        ),
        "qasper_online_required_candidate_label_missing_count": float(
            flags["missing_candidate_labels"]
        ),
        "qasper_online_required_verifier_judgment_missing_count": float(
            flags["missing_verifier_judgments"]
        ),
        "qasper_online_required_auditor_status_missing_count": float(
            flags["missing_auditor_statuses"]
        ),
        "qasper_online_required_annotation_ambiguity_missing_count": float(
            flags["missing_ambiguity_states"]
        ),
        "qasper_online_auditor_attempt_missing_count": float(
            counts["auditor_attempt_missing"]
        ),
        "qasper_online_verifier_missing_count": float(counts["verifier_missing"]),
        "qasper_unexpected_unknown_assessment_count": float(
            counts["unexpected_unknown_assessment"]
        ),
    }


def _lane_metrics(
    quality_flags: dict[str, bool],
    probe_flags: dict[str, bool],
    *,
    quality_counts: dict[str, int],
    probe_counts: dict[str, int],
) -> dict[str, float]:
    return {
        "qasper_quality_online_required_candidate_label_missing_count": float(
            quality_flags["missing_candidate_labels"]
        ),
        "qasper_quality_online_required_verifier_judgment_missing_count": float(
            quality_flags["missing_verifier_judgments"]
        ),
        "qasper_quality_online_required_auditor_status_missing_count": float(
            quality_flags["missing_auditor_statuses"]
        ),
        "qasper_quality_online_required_annotation_ambiguity_missing_count": float(
            quality_flags["missing_ambiguity_states"]
        ),
        "qasper_quality_online_auditor_attempt_missing_count": float(
            quality_counts["auditor_attempt_missing"]
        ),
        "qasper_quality_online_verifier_missing_count": float(
            quality_counts["verifier_missing"]
        ),
        "qasper_contract_probe_online_required_candidate_label_missing_count": float(
            probe_flags["missing_candidate_labels"]
        ),
        "qasper_contract_probe_online_required_verifier_judgment_missing_count": float(
            probe_flags["missing_verifier_judgments"]
        ),
        "qasper_contract_probe_online_required_auditor_status_missing_count": float(
            probe_flags["missing_auditor_statuses"]
        ),
        "qasper_contract_probe_online_required_annotation_ambiguity_missing_count": float(
            probe_flags["missing_ambiguity_states"]
        ),
        "qasper_contract_probe_online_auditor_attempt_missing_count": float(
            probe_counts["auditor_attempt_missing"]
        ),
        "qasper_contract_probe_online_verifier_missing_count": float(
            probe_counts["verifier_missing"]
        ),
        "qasper_contract_probe_unexpected_false_abstention_count": float(
            probe_counts["unexpected_false_abstentions"]
        ),
    }
