from typing import Any

from benchmark.answer_finalizer import finalize_prediction_answer


def _verified_bundle(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "items": [item],
        "metadata": {"verified_claim_support_evidence": [item]},
    }


def test_finalizer_attaches_inline_citation_from_verified_evidence():
    item = {
        "evidence_id": "page-image:deck:3",
        "source_id": "deck",
        "page_label": "3",
        "text": "Market size",
    }
    prediction: dict[str, Any] = {
        "predicted_answer": "Market size",
        "answer_type": "extractive",
        "evidence_bundle": _verified_bundle(item),
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
            "kind": "evidence",
            "evidence_id": "evidence:deck:page-image%3Adeck%3A3",
            "source_id": "deck",
            "page_label": "3",
            "span": "Market size",
        }
    ]
    assert prediction["predicted_citations"] == ["deck#page:3"]


def test_finalizer_prefers_source_backref_over_internal_uuid_source_id():
    item = {
        "evidence_id": "page-image:uuid-doc:54",
        "source_id": "9a752327-879b-4147-91a3-a6730ef9f0fd",
        "page_label": "54",
        "source_backrefs": ["OTC_NSRGY_2020#page:54"],
        "text": "Underlying trading operating profit decreased.",
    }
    prediction: dict[str, Any] = {
        "predicted_answer": "Underlying trading operating profit decreased.",
        "answer_type": "extractive",
        "evidence_bundle": _verified_bundle(item),
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
    item = {
        "evidence_id": "text-hit",
        "source_id": "9a752327-879b-4147-91a3-a6730ef9f0fd",
        "page_label": "62",
        "text": "E-commerce sales increased.",
    }
    prediction: dict[str, Any] = {
        "predicted_answer": "E-commerce sales increased.",
        "answer_type": "extractive",
        "evidence_bundle": _verified_bundle(item),
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


def test_finalizer_attaches_financebench_citation_from_canonical_source():
    item = {
        "evidence_id": "text-hit",
        "source_id": "30ce33e9-7648-4d4f-a7de-internal",
        "page_label": "42",
        "text": "The quick ratio was 0.96.",
    }
    prediction: dict[str, Any] = {
        "predicted_answer": "0.96",
        "answer_type": "extractive",
        "evidence_bundle": _verified_bundle(item),
        "scored_predicted_sources": ["MMM_2022_10K#page:42"],
        "gold_evidence": [{"source_id": "MMM_2022_10K", "page_label": "42"}],
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="financebench_plan5_text_main_current",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_scoring"] == "0.96"
    assert prediction["structured_citations"][0]["source_id"] == "MMM_2022_10K"
    assert prediction["structured_citations"][0]["page_label"] == "42"
    assert prediction["predicted_citations"] == ["MMM_2022_10K#page:42"]


def test_finalizer_falls_back_to_explicit_verified_support_after_rebind():
    support = {
        "evidence_id": "support",
        "source_id": "paper",
        "text": "We report experiments only on English data.",
    }
    prediction: dict[str, Any] = {
        "predicted_answer": "yes",
        "answer_type": "boolean",
        "question": "Do they report results only on English data?",
        "gold_evidence": [{"source_id": "paper"}],
        "evidence_bundle": {"items": [], "metadata": {}},
        "evidence_metadata": {
            "verified_claim_support_by_claim": {
                "qasper:answerability": ["evidence:paper:support"]
            },
            "verified_claim_support_evidence": [support],
        },
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="qasper",
        mode="scoring_adapter_v1",
    )

    assert prediction["predicted_citations"] == ["paper#source"]
    assert prediction["structured_citations"][0]["evidence_id"] == (
        "evidence:paper:support"
    )
