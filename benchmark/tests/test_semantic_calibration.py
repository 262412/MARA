from typing import Any

from benchmark.semantic_calibration import evaluate_semantic_calibration


def test_semantic_calibration_reports_agreement_and_coverage():
    rows: list[dict[str, Any]] = [
        {"human_pass": True, "judge_pass": True, "judge_status": "ok"},
        {"human_pass": False, "judge_pass": False, "judge_status": "ok"},
        {"human_pass": True, "judge_pass": None, "judge_status": "error"},
    ]

    result = evaluate_semantic_calibration(rows)

    assert result == {
        "contract_id": "semantic_judge_calibration_v1",
        "num_examples": 3,
        "num_judged": 2,
        "agreement": 1.0,
        "coverage": 2 / 3,
        "sample_count_gate": False,
        "agreement_gate": True,
        "coverage_gate": False,
        "release_gate": False,
    }


def test_semantic_calibration_requires_frozen_200_example_set():
    rows: list[dict[str, Any]] = [
        {"human_pass": True, "judge_pass": True, "judge_status": "ok"}
        for _ in range(199)
    ]

    result = evaluate_semantic_calibration(rows)

    assert result["agreement_gate"] is True
    assert result["coverage_gate"] is True
    assert result["sample_count_gate"] is False
    assert result["release_gate"] is False
