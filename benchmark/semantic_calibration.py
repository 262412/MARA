from __future__ import annotations

from typing import Any

SEMANTIC_CALIBRATION_CONTRACT = "semantic_judge_calibration_v1"
MIN_CALIBRATION_AGREEMENT = 0.90
MIN_CALIBRATION_COVERAGE = 0.995
MIN_CALIBRATION_EXAMPLES = 200


def evaluate_semantic_calibration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    judged = [
        row
        for row in rows
        if row.get("judge_status") == "ok" and row.get("judge_pass") is not None
    ]
    agreement = (
        sum(
            bool(row.get("human_pass")) == bool(row.get("judge_pass")) for row in judged
        )
        / len(judged)
        if judged
        else 0.0
    )
    coverage = len(judged) / len(rows) if rows else 0.0
    agreement_gate = agreement >= MIN_CALIBRATION_AGREEMENT
    coverage_gate = coverage >= MIN_CALIBRATION_COVERAGE
    sample_count_gate = len(rows) >= MIN_CALIBRATION_EXAMPLES
    return {
        "contract_id": SEMANTIC_CALIBRATION_CONTRACT,
        "num_examples": len(rows),
        "num_judged": len(judged),
        "agreement": agreement,
        "coverage": coverage,
        "sample_count_gate": sample_count_gate,
        "agreement_gate": agreement_gate,
        "coverage_gate": coverage_gate,
        "release_gate": sample_count_gate and agreement_gate and coverage_gate,
    }
