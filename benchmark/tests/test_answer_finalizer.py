import json
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


def test_finalizer_emits_canonical_qasper_boolean_without_rationale():
    prediction: dict[str, Any] = {
        "question": "Was retrieval used?",
        "predicted_answer": "True. The method section says retrieval was used.",
        "answer_type": "boolean",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="qasper-dev",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == "yes"
    assert prediction["answer_for_scoring"] == "yes"


def test_finalizer_emits_canonical_qasper_unanswerable():
    prediction: dict[str, Any] = {
        "question": "Was a graph retriever evaluated?",
        "predicted_answer": "Insufficient evidence in the paper.",
        "answer_type": "unanswerable",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="qasper-dev",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == "unanswerable"
    assert prediction["answer_for_scoring"] == "unanswerable"


def test_finalizer_enforces_qasper_typed_label_contract():
    prediction: dict[str, Any] = {
        "question": "What absolute gain was reported?",
        "predicted_answer": "The paper reports a 99.53% gain.",
        "answer_type": "unanswerable",
    }
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_typed_v2",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == "unanswerable"
    assert prediction["answer_for_scoring"] == "unanswerable"
    assert prediction["answer_finalization"]["qasper_contract_normalized"] is True


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
    assert prediction["answer_for_user"] == prediction["answer_for_scoring"]


def test_finalizer_extracts_first_valid_ragtruth_object_from_repeated_prose():
    prediction: dict[str, Any] = {
        "predicted_answer": (
            "The response is supported.\n"
            '{"hallucination list": []}'
            "The response is supported.\n"
            '{"hallucination list": []}'
        ),
        "answer_type": "verification",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="ragtruth",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == '{"hallucination list": []}'
    assert prediction["answer_for_scoring"] == '{"hallucination list": []}'
    assert prediction["answer_finalization"]["task_contract_status"] == "ok"


def test_finalizer_repairs_ragtruth_python_dict_once_without_changing_spans():
    prediction: dict[str, Any] = {
        "predicted_answer": "{'hallucination list': ['profit doubled']}",
        "gold_evidence": [],
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="ragtruth",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_scoring"] == (
        '{"hallucination list": ["profit doubled"]}'
    )
    assert prediction["answer_finalization"]["ragtruth_json_repair_attempted"] is True
    assert prediction["answer_finalization"]["ragtruth_json_repair_succeeded"] is True


def test_finalizer_repairs_unescaped_json_newline_without_changing_span():
    prediction: dict[str, Any] = {
        "predicted_answer": (
            '{"hallucination list": ["first unsupported line\n'
            'second unsupported line"]}'
        ),
        "gold_evidence": [],
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="ragtruth",
        mode="scoring_adapter_v1",
    )

    assert json.loads(prediction["answer_for_scoring"]) == {
        "hallucination list": ["first unsupported line\nsecond unsupported line"]
    }
    assert prediction["answer_finalization"]["ragtruth_json_repair_attempted"] is True
    assert prediction["answer_finalization"]["ragtruth_json_repair_succeeded"] is True


def test_finalizer_repairs_first_of_repeated_json_objects_with_raw_newlines():
    prediction: dict[str, Any] = {
        "predicted_answer": (
            '{"hallucination list": ["first unsupported line\n'
            'second unsupported line"]}'
            '{"hallucination list": ["first unsupported line\n'
            'second unsupported line"]}'
        ),
        "gold_evidence": [],
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="ragtruth",
        mode="scoring_adapter_v1",
    )

    assert json.loads(prediction["answer_for_scoring"]) == {
        "hallucination list": ["first unsupported line\nsecond unsupported line"]
    }
    assert prediction["answer_finalization"]["ragtruth_json_repair_attempted"] is True
    assert prediction["answer_finalization"]["ragtruth_json_repair_succeeded"] is True


def test_finalizer_does_not_coerce_ragtruth_prose_to_clean_json():
    prediction: dict[str, Any] = {
        "predicted_answer": "The response is fully supported.",
        "gold_evidence": [],
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="ragtruth",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == ""
    assert prediction["answer_for_scoring"] == ""
    assert prediction["answer_finalization"]["ragtruth_json_repair_attempted"] is True
    assert prediction["answer_finalization"]["ragtruth_json_repair_succeeded"] is False
    assert prediction["answer_finalization"]["task_contract_status"] == "error"


def test_finalizer_removes_exact_repeated_visual_answer_halves():
    examples = {
        "4.54.5": "4.5",
        "50%50%": "50%",
        "Andreasen apparatusAndreasen apparatus": "Andreasen apparatus",
        "1212": "12",
        "66": "6",
        "xx": "x",
    }

    for raw_answer, expected in examples.items():
        prediction: dict[str, Any] = {
            "question": "What value is shown?",
            "predicted_answer": raw_answer,
            "answer_type": "extractive",
        }

        finalize_prediction_answer(
            prediction,
            dataset_name="slidevqa",
            mode="scoring_adapter_v1",
        )

        assert prediction["answer_for_user"] == expected
        assert prediction["answer_for_scoring"] == expected
        assert prediction["answer_finalization"]["repetition_removed"] is True


def test_finalizer_preserves_repeated_digits_for_year_question():
    prediction: dict[str, Any] = {
        "question": "In what year was the charter signed?",
        "predicted_answer": "1212",
        "answer_type": "date",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="slidevqa",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == "1212"
    assert prediction["answer_for_scoring"] == "1212"
    assert prediction["answer_finalization"]["repetition_removed"] is False


def test_finalizer_deduplicates_list_items_and_unions_inline_citations():
    prediction: dict[str, Any] = {
        "question": "Which people were nominated?",
        "predicted_answer": "Ada [1], Grace [2], Ada [3]",
        "answer_type": "list_qa",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="alce-qampari",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == "Ada [1][3], Grace [2]"
    assert prediction["answer_for_scoring"] == "Ada, Grace"
    assert prediction["answer_finalization"]["repetition_removed"] is True
    assert (
        prediction["answer_finalization"]["repetition_kind"] == "normalized_list_items"
    )


def test_finalizer_preserves_list_repetition_when_question_requests_it():
    prediction: dict[str, Any] = {
        "question": "Repeat each label exactly as shown.",
        "predicted_answer": "A, A, B",
        "answer_type": "list_qa",
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="alce-qampari",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == "A, A, B"
    assert prediction["answer_finalization"]["repetition_removed"] is False


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


def test_finalizer_canonicalizes_existing_financebench_uuid_citation():
    prediction: dict[str, Any] = {
        "predicted_answer": "The cash conversion cycle is not provided.",
        "answer_type": "extractive",
        "structured_citations": [
            {
                "evidence_id": "a99fe487-90ba-45b2-810d-fef2fddb5ac8",
                "source_id": "de95827e-87fb-4151-99bb-338b2d79f22c",
                "page_label": "60",
                "span": "The cash conversion cycle is not provided.",
            }
        ],
        "predicted_citations": ["de95827e-87fb-4151-99bb-338b2d79f22c#page:60"],
        "evidence_bundle": {
            "items": [
                {
                    "source_id": "de95827e-87fb-4151-99bb-338b2d79f22c",
                    "page_label": "60",
                    "source_backrefs": ["de95827e-87fb-4151-99bb-338b2d79f22c#page:60"],
                }
            ]
        },
        "predicted_sources": [
            "GENERALMILLS_2019_10K#page:60",
            "GENERALMILLS_2019_10K#page:3",
        ],
        "gold_evidence": [{"source_id": "GENERALMILLS_2019_10K", "page_label": "60"}],
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="financebench_plan5_text_main_current",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == (
        "The cash conversion cycle is not provided. GENERALMILLS_2019_10K#page:60"
    )
    assert prediction["structured_citations"][0]["source_id"] == (
        "GENERALMILLS_2019_10K"
    )
    assert prediction["structured_citations"][0]["page_label"] == "60"
    assert prediction["predicted_citations"] == ["GENERALMILLS_2019_10K#page:60"]
