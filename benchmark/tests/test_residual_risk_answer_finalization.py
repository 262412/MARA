from typing import Any

from benchmark.answer_finalizer import finalize_prediction_answer


def test_finalizer_normalizes_explicit_qasper_insufficiency_without_gold_type():
    prediction: dict[str, Any] = {
        "question": "What was the baseline?",
        "predicted_answer": "Insufficient evidence in the retrieved paper.",
        "answer_type": "free_text",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="qasper-dev",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == "unanswerable"
    assert prediction["answer_for_scoring"] == "unanswerable"


def test_finalizer_removes_short_repeated_decorated_numeric_answer():
    prediction: dict[str, Any] = {
        "question": "What was net sales?",
        "predicted_answer": "$38$38",
        "answer_type": "numeric",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="financebench",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == "$38"
    assert prediction["answer_for_scoring"] == "$38"
    assert prediction["answer_finalization"]["repetition_removed"] is True
