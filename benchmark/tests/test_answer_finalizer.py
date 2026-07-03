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


def test_finalizer_extracts_structured_answer_and_renders_inline_citation():
    prediction: dict[str, Any] = {
        "predicted_answer": (
            '{"answer": "Market size", "citations": ['
            '{"source_id": "deck", "page_label": "3", "span": "Market size"}]}'
        ),
        "answer_type": "extractive",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="slidevqa_test_shard0_multimodal",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == "Market size deck#page:3"
    assert prediction["answer_for_scoring"] == "Market size"
    assert prediction["structured_citations"] == [
        {"source_id": "deck", "page_label": "3", "span": "Market size"}
    ]
    assert prediction["predicted_citations"] == ["deck#page:3"]


def test_finalizer_recovers_answer_from_truncated_visual_json_without_scoring_brace():
    prediction: dict[str, Any] = {
        "predicted_answer": (
            '{\n"answer": "CARE. CONNECT. CAMPAIGN.",\n"citations": [\n'
            '{"evidence_id": "page-image:deck'
        ),
        "answer_type": "extractive",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="slidevqa_test_shard0_multimodal",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_scoring"] == "CARE. CONNECT. CAMPAIGN"
    assert prediction["answer_finalization"]["source"] == "truncated_structured_adapter"
    assert prediction.get("structured_citations") is None
    assert prediction.get("predicted_citations", []) == []


def test_finalizer_attaches_inline_citation_from_evidence_metadata():
    prediction: dict[str, Any] = {
        "predicted_answer": "Market size",
        "answer_type": "extractive",
        "evidence_bundle": {
            "items": [
                {
                    "evidence_id": "page-image:deck:3",
                    "source_id": "deck",
                    "page_label": "3",
                    "text": "Market size",
                }
            ]
        },
        "retrieved_hits": [],
        "predicted_sources": [],
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="slidevqa_test_shard0_multimodal",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == "Market size deck#page:3"
    assert prediction["answer_for_scoring"] == "Market size"
    assert prediction["structured_citations"] == [
        {
            "evidence_id": "page-image:deck:3",
            "source_id": "deck",
            "page_label": "3",
            "span": "Market size",
        }
    ]
    assert prediction["predicted_citations"] == ["deck#page:3"]


def test_finalizer_prefers_source_backref_over_internal_uuid_source_id():
    prediction: dict[str, Any] = {
        "predicted_answer": "Underlying trading operating profit decreased.",
        "answer_type": "extractive",
        "evidence_bundle": {
            "items": [
                {
                    "evidence_id": "page-image:uuid-doc:54",
                    "source_id": "9a752327-879b-4147-91a3-a6730ef9f0fd",
                    "page_label": "54",
                    "source_backrefs": ["OTC_NSRGY_2020#page:54"],
                    "text": "Underlying trading operating profit decreased.",
                }
            ]
        },
        "predicted_sources": ["OTC_NSRGY_2020#page:54"],
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="mmdocrag_dev15_available_docs_multimodal",
        mode="scoring_adapter_v1",
    )

    assert prediction["structured_citations"][0]["source_id"] == "OTC_NSRGY_2020"
    assert prediction["structured_citations"][0]["page_label"] == "54"
    assert prediction["predicted_citations"] == ["OTC_NSRGY_2020#page:54"]


def test_finalizer_uses_canonical_predicted_source_when_backref_missing():
    prediction: dict[str, Any] = {
        "predicted_answer": "E-commerce sales increased.",
        "answer_type": "extractive",
        "evidence_bundle": {
            "items": [
                {
                    "evidence_id": "text-hit",
                    "source_id": "9a752327-879b-4147-91a3-a6730ef9f0fd",
                    "page_label": "62",
                    "text": "E-commerce sales increased.",
                }
            ]
        },
        "predicted_sources": ["OTC_NSRGY_2020#page:62"],
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="mmdocrag_dev15_available_docs_multimodal",
        mode="scoring_adapter_v1",
    )

    assert prediction["structured_citations"][0]["source_id"] == "OTC_NSRGY_2020"
    assert prediction["structured_citations"][0]["page_label"] == "62"
    assert prediction["predicted_citations"] == ["OTC_NSRGY_2020#page:62"]
