from benchmark.semantic_answer import semantic_answer_metrics


def test_numeric_score_inherits_missing_gold_scale_from_question():
    metrics, metadata = semantic_answer_metrics(
        {
            "question": "What was working capital in 2021, in USD millions?",
            "answer_type": "numeric",
            "predicted_answer": "$5,818 million",
            "gold_answers": ["$5,818"],
        }
    )

    assert metrics["semantic_answer_f1"] == 1.0
    assert metadata["core_contradiction"] is False


def test_numeric_score_inherits_missing_prediction_scale_from_question():
    metrics, metadata = semantic_answer_metrics(
        {
            "question": "What was working capital in 2021, in USD millions?",
            "answer_type": "numeric",
            "predicted_answer": "$5,818",
            "gold_answers": ["$5,818 million"],
        }
    )

    assert metrics["semantic_answer_f1"] == 1.0
    assert metadata["core_contradiction"] is False


def test_numeric_score_keeps_explicit_scale_conflicts_fatal():
    metrics, metadata = semantic_answer_metrics(
        {
            "question": "What was working capital in 2021, in USD millions?",
            "answer_type": "numeric",
            "predicted_answer": "$5,818 billion",
            "gold_answers": ["$5,818"],
        }
    )

    assert metrics["semantic_answer_f1"] == 0.0
    assert metadata["core_contradiction"] is True
