from __future__ import annotations

from typing import Any

from benchmark.qasper_candidate_state import select_answerability_candidate


def test_truncated_math_fragment_falls_back_to_pre_verification_answer():
    substantive_answer = (
        "The method uses labeled features, class distribution, and neutral features."
    )
    prediction: dict[str, Any] = {
        "question": "What background knowledge does the method use?",
        "predicted_answer": "$$ \\text{",
        "answer_for_scoring": "$$ \\text{",
        "evidence_metadata": {
            "pre_guardrail_answer": "$$ \\text{",
            "pre_verification_answer": f"{substantive_answer}\n\n$$\n\\text{{",
        },
    }

    candidate = select_answerability_candidate(prediction)

    assert candidate.product_abstained is True
    assert candidate.candidate_for_answerability == substantive_answer
    assert candidate.input_candidate_kind == "pre_verification_answer"
    assert candidate.recovery_attempted is True
