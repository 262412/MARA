import json
from typing import Any

from benchmark.dataset_native_scores import native_metrics_for_prediction


def test_ragtruth_native_score_uses_hallucination_spans_not_gold_answer_f1():
    prediction: dict[str, Any] = {
        "predicted_answer": json.dumps(
            {"hallucination list": ["profit doubled"]},
        ),
        "gold_answers": ["Revenue rose and profit doubled."],
        "metrics": {"f1": 0.0},
        "example_metadata": {
            "labels": [
                {"label_type": "hallucination", "text": "profit doubled"},
                {"label_type": "supported", "text": "Revenue rose"},
            ]
        },
    }

    metrics, metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="ragtruth-plan5",
    )

    assert metadata["contract_id"] == "ragtruth_hallucination_spans_v1"
    assert metadata["primary_metric"] == "ragtruth_hallucination_span_f1"
    assert metrics["ragtruth_hallucination_span_precision"] == 1.0
    assert metrics["ragtruth_hallucination_span_recall"] == 1.0
    assert metrics["ragtruth_hallucination_span_f1"] == 1.0
    assert metrics["ragtruth_json_valid"] == 1.0
    assert metrics["ragtruth_positive_detected"] == 1.0
    assert metrics["ragtruth_clean_specificity"] is None
    assert metrics["native_score"] == 1.0


def test_ragtruth_native_score_returns_zero_when_no_spans_match():
    prediction: dict[str, Any] = {
        "predicted_answer": json.dumps({"hallucination list": ["revenue fell"]}),
        "gold_answers": ["The response being verified."],
        "metrics": {"f1": 0.0},
        "example_metadata": {
            "labels": [{"label_type": "hallucination", "text": "profit doubled"}]
        },
    }

    metrics, _metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="ragtruth-plan5",
    )

    assert metrics["ragtruth_hallucination_span_precision"] == 0.0
    assert metrics["ragtruth_hallucination_span_recall"] == 0.0
    assert metrics["ragtruth_hallucination_span_f1"] == 0.0
    assert metrics["native_score"] == 0.0


def test_ragtruth_native_score_reports_invalid_json_separately_from_empty_list():
    prediction: dict[str, Any] = {
        "predicted_answer": "The response looks supported.",
        "gold_answers": ["The response being verified."],
        "metrics": {"f1": 0.0},
        "example_metadata": {"labels": []},
    }

    metrics, _metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="ragtruth-plan5",
    )

    assert metrics["ragtruth_json_valid"] == 0.0
    assert metrics["ragtruth_positive_detected"] is None
    assert metrics["ragtruth_clean_specificity"] == 0.0
    assert metrics["ragtruth_hallucination_span_f1"] == 0.0
    assert metrics["native_score"] == 0.0


def test_ragtruth_clean_specificity_accepts_valid_empty_hallucination_list():
    prediction: dict[str, Any] = {
        "predicted_answer": '{"hallucination list": []}',
        "gold_answers": ["The response being verified."],
        "metrics": {"f1": 0.0},
        "example_metadata": {"labels": []},
    }

    metrics, _metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="ragtruth-plan5",
    )

    assert metrics["ragtruth_json_valid"] == 1.0
    assert metrics["ragtruth_clean_specificity"] == 1.0


def test_ragtruth_native_score_accepts_official_baseless_label_types():
    prediction: dict[str, Any] = {
        "predicted_answer": json.dumps(
            {"hallucination list": ["supporting brain function"]}
        ),
        "gold_answers": ["The response being verified."],
        "metrics": {"f1": 0.0},
        "example_metadata": {
            "labels": [
                {
                    "label_type": "Evident Baseless Info",
                    "text": "supporting brain function",
                    "implicit_true": False,
                    "due_to_null": False,
                }
            ]
        },
    }

    metrics, _metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="ragtruth-plan5",
    )

    assert metrics["ragtruth_hallucination_span_precision"] == 1.0
    assert metrics["ragtruth_hallucination_span_recall"] == 1.0
    assert metrics["ragtruth_hallucination_span_f1"] == 1.0
    assert metrics["native_score"] == 1.0
