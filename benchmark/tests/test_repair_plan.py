import pytest

from benchmark.repair_plan import (
    ABLATION_PHASES,
    CAPABILITY_TARGETS,
    CONTRACT_GATES,
    PAIRED_REGRESSION_GATES,
    evaluate_release_gates,
    formal_full_run_allowed,
    validate_ablation_progression,
)


def test_ablation_phases_are_cumulative_and_fixed_from_a_through_g():
    assert list(ABLATION_PHASES) == list("ABCDEFG")
    assert ABLATION_PHASES["A"].features == ()
    assert "semantic_answer_scoring" in ABLATION_PHASES["B"].features
    assert "claim_aggregation" in ABLATION_PHASES["C"].features
    assert "constrained_mmr" in ABLATION_PHASES["D"].features
    assert "second_round_retrieval" in ABLATION_PHASES["E"].features
    assert "deterministic_calculation" in ABLATION_PHASES["F"].features
    assert "controller_crag_integration" in ABLATION_PHASES["G"].features
    for previous, current in zip("ABCDEF", "BCDEFG"):
        assert set(ABLATION_PHASES[previous].features) <= set(
            ABLATION_PHASES[current].features
        )


def test_ablation_progression_rejects_skipped_or_reordered_phases():
    validate_ablation_progression(list("ABCDE"))

    with pytest.raises(ValueError, match="fixed prefix"):
        validate_ablation_progression(["A", "B", "D"])


def test_formal_full_run_requires_phase_g_and_all_preflight_gates():
    assert formal_full_run_allowed(
        phase="G",
        unit_tests_passed=True,
        fixed_sample_passed=True,
        semantic_calibration_passed=True,
    )
    assert not formal_full_run_allowed(
        phase="F",
        unit_tests_passed=True,
        fixed_sample_passed=True,
        semantic_calibration_passed=True,
    )
    assert not formal_full_run_allowed(
        phase="G",
        unit_tests_passed=True,
        fixed_sample_passed=False,
        semantic_calibration_passed=True,
    )


def test_release_gates_report_metric_and_failure_stage_without_reweighting():
    result = evaluate_release_gates(
        phase_b={"avg_semantic_answer_f1": 0.40},
        phase_g={
            "avg_semantic_answer_f1": 0.49,
            "semantic_calibration_examples": 200,
            "semantic_calibration_agreement": 0.91,
            "semantic_judge_coverage": 0.997,
            "slidevqa_duplicate_ratio": 0.04,
            "ragtruth_json_valid": 0.995,
        },
        paired_semantic_ci_low=0.01,
    )

    assert result["semantic_f1_delta_pp"]["passed"] is True
    assert result["semantic_f1_delta_pp"]["value"] == 9.0
    assert result["semantic_f1_ci_low"]["passed"] is True
    assert result["slidevqa_duplicate_ratio"]["passed"] is True
    assert result["ragtruth_positive_recall"]["passed"] is False
    assert result["ragtruth_positive_recall"]["status"] == "missing"
    assert result["ragtruth_positive_recall"]["failure_stage"] == "task_contract"


def test_release_gates_separate_contract_regression_and_capability_targets():
    assert {gate.category for gate in CONTRACT_GATES} == {"contract"}
    assert {gate.category for gate in PAIRED_REGRESSION_GATES} == {"paired_regression"}
    assert {gate.category for gate in CAPABILITY_TARGETS} == {"capability_target"}

    result = evaluate_release_gates(
        phase_b={"avg_semantic_answer_f1": 0.4},
        phase_g={"avg_semantic_answer_f1": 0.49},
        paired_semantic_ci_low=0.01,
    )

    assert result["token_f1_rescore_delta"]["release_blocking"] is True
    assert result["financebench_native_numeric"]["release_blocking"] is False
    assert result["financebench_native_numeric"]["category"] == "capability_target"


def test_release_gates_reject_mismatched_paired_inputs():
    with pytest.raises(ValueError, match="paired benchmark input mismatch"):
        evaluate_release_gates(
            phase_b={
                "avg_semantic_answer_f1": 0.40,
                "run_provenance": {
                    "paired_input_hash": "phase-b",
                    "index_contract": f"sha256:{'a' * 64}",
                },
            },
            phase_g={
                "avg_semantic_answer_f1": 0.49,
                "run_provenance": {
                    "paired_input_hash": "phase-g",
                    "index_contract": f"sha256:{'a' * 64}",
                },
            },
            paired_semantic_ci_low=0.01,
        )


def test_release_gates_allow_different_code_with_matching_paired_inputs():
    result = evaluate_release_gates(
        phase_b={
            "avg_semantic_answer_f1": 0.40,
            "run_provenance": {
                "contract_hash": "baseline-code",
                "paired_input_hash": "frozen-input",
                "index_contract": f"sha256:{'a' * 64}",
            },
        },
        phase_g={
            "avg_semantic_answer_f1": 0.49,
            "run_provenance": {
                "contract_hash": "candidate-code",
                "paired_input_hash": "frozen-input",
                "index_contract": f"sha256:{'a' * 64}",
            },
        },
        paired_semantic_ci_low=0.01,
    )

    assert result["semantic_f1_delta_pp"]["passed"] is True
