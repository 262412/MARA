from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from ktem.docqa.evidence_identity import identity_of
from ktem.reasoning.mara_ragtruth_answering import route_ragtruth_answer

from benchmark.alce_answer_grounding import apply_alce_answer_grounding
from benchmark.answer_finalizer import finalize_prediction_answer


class _SequenceLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)

    def __call__(self, messages, **kwargs):
        del messages, kwargs
        return SimpleNamespace(text=next(self.responses))


def _prediction(
    answer: str,
    item: dict[str, Any],
    *,
    dataset_name: str,
) -> dict[str, Any]:
    return {
        "predicted_answer": answer,
        "answer_type": "citation_qa" if "alce" in dataset_name else "verification",
        "gold_evidence": [{"source_id": item.get("source_id", "report")}],
        "evidence_bundle": {"items": [item], "metadata": {}},
        "evidence_metadata": {},
    }


def test_alce_producer_to_finalizer_projects_only_accepted_grounding():
    item = {
        "evidence_id": "speaker-range",
        "source_id": "report",
        "page_label": "5",
        "text": "John Boehner was the Speaker of the US House.",
    }
    answer, grounding, _ = apply_alce_answer_grounding(
        suite_name="alce-asqa",
        llm_factory=lambda: _SequenceLLM(
            ['{"verdict":"supported","answer":"John Boehner",' '"evidence_index":0}']
        ),
        question="Who was Speaker?",
        candidate_answer="John Boehner",
        evidence_items=[item],
    )
    prediction = _prediction(answer, item, dataset_name="alce-asqa")
    prediction["evidence_metadata"]["alce_answer_grounding"] = grounding

    finalize_prediction_answer(
        prediction,
        dataset_name="alce-asqa",
        mode="scoring_adapter_v1",
    )

    identity = identity_of(item).key
    assert grounding["status"] == "ok"
    assert prediction["structured_citations"]
    assert prediction["evidence_metadata"]["verified_claim_support_by_claim"] == {
        "alce:grounding": [identity]
    }
    assert [
        identity_of(value).key
        for value in prediction["evidence_metadata"]["emitted_citation_evidence"]
    ] == [identity]


def test_alce_rejected_or_unsupported_grounding_fails_closed():
    item = {
        "evidence_id": "speaker-range",
        "source_id": "report",
        "page_label": "5",
        "text": "John Boehner was the Speaker of the US House.",
    }
    for trace in (
        {
            "status": "rejected_inconsistent_supported_answer",
            "verdict": "supported",
            "evidence_id": "speaker-range",
            "answer_changed": False,
        },
        {
            "status": "ok",
            "verdict": "corrected",
            "evidence_id": "speaker-range",
            "answer_changed": True,
        },
        {
            "status": "unknown",
            "verdict": "supported",
            "evidence_id": "speaker-range",
            "answer_changed": False,
        },
    ):
        prediction = _prediction("John Boehner", item, dataset_name="alce-asqa")
        prediction["evidence_metadata"]["alce_answer_grounding"] = trace

        finalize_prediction_answer(
            prediction,
            dataset_name="alce-asqa",
            mode="scoring_adapter_v1",
        )

        assert prediction.get("structured_citations", []) == []
        assert (
            prediction["evidence_metadata"].get("verified_claim_support_evidence", [])
            == []
        )
        assert (
            prediction["evidence_metadata"].get("emitted_citation_evidence", []) == []
        )


def test_alce_accepts_explicit_final_answer_in_explanatory_candidate():
    item = {
        "evidence_id": "music-span",
        "source_id": "report",
        "text": "The performers were Simon & Garfunkel.",
    }
    candidate = "The evidence identifies the performers.\nAnswer: Simon & Garfunkel"
    answer, grounding, _ = apply_alce_answer_grounding(
        suite_name="alce-asqa",
        llm_factory=lambda: _SequenceLLM(
            [
                '{"verdict":"supported","answer":"Simon & Garfunkel",'
                '"evidence_index":0}'
            ]
        ),
        question="Who performed?",
        candidate_answer=candidate,
        evidence_items=[item],
    )
    prediction = _prediction(answer, item, dataset_name="alce-asqa")
    prediction["evidence_metadata"]["alce_answer_grounding"] = grounding

    finalize_prediction_answer(
        prediction,
        dataset_name="alce-asqa",
        mode="scoring_adapter_v1",
    )

    assert grounding["status"] == "ok"
    assert grounding["grounded_answer"] == "Simon & Garfunkel"
    assert prediction["structured_citations"]


def test_alce_body_mention_of_short_answer_is_not_consistent():
    item = {
        "evidence_id": "music-span",
        "source_id": "report",
        "text": "The performers were Simon & Garfunkel.",
    }
    candidate = (
        "The evidence mentions Simon & Garfunkel in passing but does not answer "
        "the question."
    )
    _, grounding, _ = apply_alce_answer_grounding(
        suite_name="alce-asqa",
        llm_factory=lambda: _SequenceLLM(
            [
                '{"verdict":"supported","answer":"Simon & Garfunkel",'
                '"evidence_index":0}'
            ]
        ),
        question="Who performed?",
        candidate_answer=candidate,
        evidence_items=[item],
    )

    assert grounding["status"] == "rejected_inconsistent_supported_answer"


def test_alce_final_answer_mismatch_or_ambiguous_evidence_fails_closed():
    first = {
        "evidence_id": "speaker-range",
        "source_id": "report-a",
        "text": "John Boehner was the Speaker.",
    }
    second = {
        "evidence_id": "speaker-range",
        "source_id": "report-b",
        "text": "John Boehner was the Speaker.",
    }
    mismatch = _prediction("Paul Ryan", first, dataset_name="alce-asqa")
    mismatch["evidence_metadata"]["alce_answer_grounding"] = {
        "status": "ok",
        "verdict": "supported",
        "evidence_id": "speaker-range",
        "grounded_answer": "John Boehner",
        "answer_changed": False,
    }
    ambiguous = _prediction("John Boehner", first, dataset_name="alce-asqa")
    ambiguous["evidence_bundle"]["items"].append(second)
    ambiguous["evidence_metadata"]["alce_answer_grounding"] = {
        "status": "ok",
        "verdict": "supported",
        "evidence_id": "speaker-range",
        "answer_changed": False,
    }

    for prediction in (mismatch, ambiguous):
        finalize_prediction_answer(
            prediction,
            dataset_name="alce-asqa",
            mode="scoring_adapter_v1",
        )

        assert prediction.get("structured_citations", []) == []
        assert (
            prediction["evidence_metadata"].get("verified_claim_support_evidence", [])
            == []
        )


def test_alce_old_trace_without_grounded_answer_fails_closed():
    item = {
        "evidence_id": "speaker-range",
        "source_id": "report",
        "text": "John Boehner was the Speaker.",
    }
    prediction = _prediction("John Boehner", item, dataset_name="alce-asqa")
    prediction["evidence_metadata"]["alce_answer_grounding"] = {
        "status": "ok",
        "verdict": "supported",
        "evidence_id": "speaker-range",
        "answer": "John Boehner",
        "answer_changed": False,
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="alce-asqa",
        mode="scoring_adapter_v1",
    )

    assert prediction.get("structured_citations", []) == []
    assert (
        prediction["evidence_metadata"].get("verified_claim_support_evidence", []) == []
    )


def _ragtruth_prompt(source: str, response: str) -> str:
    return (
        "Below are related passages:\n"
        f"{source}\n\n"
        "Below is an answer:\n"
        f"{response}\n\n"
        'Return exactly one JSON object with the key "hallucination list".\n'
    )


def _ragtruth_prediction(
    answer: str,
    item: dict[str, Any] | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "predicted_answer": answer,
        "answer_type": "verification",
        "evidence_bundle": {
            "items": [item] if item is not None else [],
            "metadata": metadata,
        },
        "evidence_metadata": {},
    }


def test_ragtruth_producer_bridges_supported_claim_out_of_band_without_json_change():
    source = "Alice won the race."
    item = {
        "evidence_id": "source-span",
        "source_id": "doc-1",
        "text": source,
    }
    bundle = SimpleNamespace(items=[item], metadata={})
    answer = route_ragtruth_answer(
        SimpleNamespace(
            answering_pipeline=SimpleNamespace(
                llm=_SequenceLLM(
                    [
                        '{"hallucination list": []}',
                        '{"0":"supported"}',
                    ]
                )
            )
        ),
        SimpleNamespace(
            origin="benchmark",
            verification_domain="ragtruth",
            prompt=_ragtruth_prompt(source, source),
        ),
        bundle,
    )
    assert answer is not None
    prediction = _ragtruth_prediction(answer, item, bundle.metadata)

    finalize_prediction_answer(
        prediction,
        dataset_name="ragtruth",
        mode="scoring_adapter_v1",
    )

    identity = identity_of(item).key
    assert bundle.metadata["ragtruth_source_evidence_id"] == identity
    assert prediction["answer_for_scoring"] == answer
    assert json.loads(prediction["answer_for_scoring"]) == {"hallucination list": []}
    assert "citations" not in json.loads(prediction["answer_for_scoring"])
    assert prediction["evidence_metadata"]["verified_claim_support_by_claim"] == {
        "ragtruth:claim:0": [identity]
    }
    assert [
        identity_of(value).key
        for value in prediction["evidence_metadata"]["emitted_citation_evidence"]
    ] == [identity]


def test_ragtruth_unsupported_or_missing_claim_evidence_never_projects():
    item = {
        "evidence_id": "source-span",
        "source_id": "doc-1",
        "text": "Alice won the race.",
    }
    unsupported = _ragtruth_prediction(
        '{"hallucination list": ["Bob won the race."]}',
        item,
        {
            "ragtruth_claims": ["Bob won the race."],
            "ragtruth_supported_claim_indices": [],
            "ragtruth_emitted_claim_indices": [0],
        },
    )
    missing = _ragtruth_prediction(
        '{"hallucination list": []}',
        None,
        {
            "ragtruth_claims": ["Alice won the race."],
            "ragtruth_supported_claim_indices": [0],
            "ragtruth_emitted_claim_indices": [],
            "ragtruth_source_evidence_id": "source-span",
        },
    )

    for prediction in (unsupported, missing):
        finalize_prediction_answer(
            prediction,
            dataset_name="ragtruth",
            mode="scoring_adapter_v1",
        )

        assert prediction.get("structured_citations", []) == []
        assert (
            prediction["evidence_metadata"].get("verified_claim_support_evidence", [])
            == []
        )
        assert (
            prediction["evidence_metadata"].get("emitted_citation_evidence", []) == []
        )


def test_ragtruth_out_of_range_or_ambiguous_claim_evidence_fails_closed():
    first = {
        "evidence_id": "source-span",
        "source_id": "doc-1",
        "text": "Alice won the race.",
    }
    second = {
        "evidence_id": "source-span",
        "source_id": "doc-2",
        "text": "Alice won the race.",
    }
    out_of_range = _ragtruth_prediction(
        '{"hallucination list": []}',
        first,
        {
            "ragtruth_claims": ["Alice won the race."],
            "ragtruth_supported_claim_indices": [1],
            "ragtruth_emitted_claim_indices": [],
            "ragtruth_source_evidence_id": "source-span",
        },
    )
    ambiguous = _ragtruth_prediction(
        '{"hallucination list": []}',
        first,
        {
            "ragtruth_claims": ["Alice won the race."],
            "ragtruth_supported_claim_indices": [0],
            "ragtruth_emitted_claim_indices": [],
            "ragtruth_source_evidence_id": "source-span",
        },
    )
    ambiguous["evidence_bundle"]["items"].append(second)

    for prediction in (out_of_range, ambiguous):
        finalize_prediction_answer(
            prediction,
            dataset_name="ragtruth",
            mode="scoring_adapter_v1",
        )

        assert prediction.get("structured_citations", []) == []
        assert (
            prediction["evidence_metadata"].get("verified_claim_support_evidence", [])
            == []
        )


def test_ragtruth_conflicting_metadata_sources_fail_closed():
    item = {
        "evidence_id": "source-span",
        "source_id": "doc-1",
        "text": "Alice won the race.",
    }
    prediction = _ragtruth_prediction(
        '{"hallucination list": []}',
        item,
        {
            "ragtruth_claims": ["Alice won the race."],
            "ragtruth_supported_claim_indices": [0],
            "ragtruth_emitted_claim_indices": [],
            "ragtruth_source_evidence_id": "source-span",
        },
    )
    prediction["evidence_metadata"].update(
        {
            "ragtruth_claims": ["Alice won the race."],
            "ragtruth_supported_claim_indices": [],
            "ragtruth_emitted_claim_indices": [],
            "ragtruth_source_evidence_id": "source-span",
        }
    )

    finalize_prediction_answer(
        prediction,
        dataset_name="ragtruth",
        mode="scoring_adapter_v1",
    )

    assert prediction.get("structured_citations", []) == []
    assert (
        prediction["evidence_metadata"].get("verified_claim_support_evidence", []) == []
    )
