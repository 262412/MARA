from typing import Any

from benchmark.answer_finalizer import finalize_prediction_answer


def test_finalizer_keeps_user_answer_and_extracts_short_scoring_answer():
    prediction: dict[str, Any] = {
        "question": "Who received the highest number of votes against?",
        "predicted_answer": (
            "Richard A. Johnson.\n\n"
            "He received the highest number of votes against according to the "
            "proxy statement [1]."
        ),
        "answer_type": "extractive",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="qasper-dev",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == prediction["predicted_answer"]
    assert prediction["answer_for_scoring"] == "Richard A. Johnson"
    assert prediction["answer_finalization"]["mode"] == "scoring_adapter_v1"
    assert prediction["answer_finalization"]["source"] == "deterministic_adapter"


def test_finalizer_uses_product_answer_when_mode_is_product():
    prediction: dict[str, Any] = {
        "predicted_answer": "Final answer: Richard A. Johnson.\n\nBecause ...",
        "answer_type": "extractive",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="qasper-dev",
        mode="product",
    )

    assert prediction["answer_for_user"] == prediction["predicted_answer"]
    assert prediction["answer_for_scoring"] == prediction["predicted_answer"]
    assert prediction["answer_finalization"]["mode"] == "product"


def test_finalizer_strips_inline_citations_for_alce_scoring():
    prediction: dict[str, Any] = {
        "question": "What policy did the paper introduce?",
        "predicted_answer": (
            "The paper introduced retrieval-augmented verification [1][2]."
        ),
        "answer_type": "citation_qa",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="alce-asqa",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_scoring"] == (
        "The paper introduced retrieval-augmented verification"
    )


def test_finalizer_removes_common_answer_presentation_prefixes():
    prediction: dict[str, Any] = {
        "question": "Who received the highest number of votes against?",
        "predicted_answer": "The answer is Richard A. Johnson.",
        "answer_type": "extractive",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="qasper-dev",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_scoring"] == "Richard A. Johnson"


def test_finalizer_keeps_yes_no_rationale_for_scoring():
    prediction: dict[str, Any] = {
        "question": "Are JnJ's FY2022 financials typical of a high growth company?",
        "predicted_answer": (
            "No. JnJ's FY2022 financials do not indicate high growth. "
            "Sales grew by only 1.3% in FY2022."
        ),
        "answer_type": "boolean",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="financebench_plan5_text_main_current",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_scoring"] == (
        "No. JnJ's FY2022 financials do not indicate high growth"
    )


def test_finalizer_keeps_yes_no_rationale_when_reason_starts_next_line():
    prediction: dict[str, Any] = {
        "question": "Are JnJ's FY2022 financials typical of a high growth company?",
        "predicted_answer": (
            "No.\n\n"
            "JnJ's FY2022 financials do not indicate high growth. "
            "Sales grew by only 1.3% in FY2022."
        ),
        "answer_type": "boolean",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="financebench_plan5_text_main_current",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_scoring"] == (
        "No. JnJ's FY2022 financials do not indicate high growth"
    )


def test_finalizer_extracts_ragtruth_json_from_markdown_answer():
    prediction: dict[str, Any] = {
        "predicted_answer": (
            "The response contains unsupported details.\n\n"
            "```json\n"
            '{"hallucination list": ["profit doubled"]}\n'
            "```"
        ),
        "answer_type": "verification",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="ragtruth-plan5",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_scoring"] == (
        '{"hallucination list": ["profit doubled"]}'
    )
