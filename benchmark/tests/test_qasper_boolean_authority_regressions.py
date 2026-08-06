from __future__ import annotations

import json
from typing import Any

import pytest

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.qasper_answerability import verify_qasper_answerability
from benchmark.qasper_evidence_identity import canonical_quote_spans
from benchmark.task_answer_contracts import (
    apply_task_answer_contract,
    synchronize_terminal_answer_state,
)


class _Verifier:
    def __init__(self, verdict: str, quote: str, evidence_ref: str = "") -> None:
        self.response = json.dumps(
            {
                "verdict": verdict,
                "evidence_ref": evidence_ref,
                "evidence_quote": quote,
            },
            ensure_ascii=False,
        )

    def __call__(self, _prompt: str, **_kwargs: Any) -> Any:
        return type("Result", (), {"text": self.response})()


def _item(evidence_id: str, text: str) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "results",
        "text": text,
    }


@pytest.mark.parametrize("candidate", ("yes", "no", "unanswerable"))
def test_unrelated_transformers_quote_never_gains_candidate_dependent_authority(
    candidate: str,
) -> None:
    question = "Is jiant compatible with models in any programming language?"
    quote = (
        "jiant provides support for a variety of model architectures, including "
        "support for HuggingFace's Transformers."
    )

    result = verify_qasper_answerability(
        _Verifier("no_complete", quote, "E1:S1"),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("jiant", quote)],
        candidate_answer=candidate,
    )

    assert result.answer == "unanswerable"
    assert result.trace["verdict"] == "insufficient_evidence"
    assert result.trace["reason"] == "polarity_authority_unproven"
    assert result.trace.get("evidence_ref", "") == ""
    assert result.trace.get("evidence_quote", "") == ""
    assert result.trace["quote_grounded"] == "false"
    assert "authoritative_quote_evidence_id" not in result.trace


def test_verifier_ref_must_bind_the_exact_contiguous_quote() -> None:
    support = _item("support", "We evaluated the model on clinical tasks.")
    distractor = _item("distractor", "The appendix lists training parameters.")

    result = verify_qasper_answerability(
        _Verifier("yes_complete", support["text"], "E2:S1"),
        question="Did the authors evaluate the model on clinical tasks?",
        answer_type="boolean",
        evidence=f"{support['text']} {distractor['text']}",
        evidence_items=[support, distractor],
        candidate_answer="unanswerable",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "evidence_ref_quote_mismatch"
    assert result.trace.get("evidence_ref", "") == ""
    assert result.trace.get("evidence_quote", "") == ""


@pytest.mark.parametrize(
    ("case_id", "question", "quote", "expected_reason"),
    (
        (
            "623676",
            "Do they show on which examples how conflict works better than attention?",
            (
                "We also show qualitative results where we can observe that our "
                "model with attention and conflict combined does better on cases "
                "where pairs are non-duplicate and has very small difference."
            ),
            "polarity_authority_unproven",
        ),
        (
            "5f2bad",
            "Do they experiment with the toolkits?",
            (
                "We present GluonCV and GluonNLP, the deep learning toolkits for "
                "computer vision and natural language processing based on Apache "
                "MXNet (incubating)."
            ),
            "polarity_authority_unproven",
        ),
        (
            "50cb50",
            (
                "Do they experiment with their proposed model on any other "
                "dataset other than MovieQA?"
            ),
            "We mainly focus on the MovieQA dataset to train and evaluate our model.",
            "other_than_alternative_unproven",
        ),
    ),
)
def test_opposite_polarity_requires_quote_local_semantic_authority(
    case_id: str,
    question: str,
    quote: str,
    expected_reason: str,
) -> None:
    result = verify_qasper_answerability(
        _Verifier("no_complete", quote),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item(case_id, quote)],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["verdict"] == "insufficient_evidence"
    assert result.trace["action"] == "abstained_insufficient_evidence"
    assert result.trace["reason"] == expected_reason
    assert "authoritative_quote_evidence_id" not in result.trace
    assert "authoritative_quote_span_id" not in result.trace
    assert not (
        result.trace["reason"] == "grounded_complete_proposition"
        and result.answer == "unanswerable"
    )


def test_other_than_pitch_requires_an_explicit_alternative() -> None:
    question = (
        "Are there elements, other than pitch, that can potentially result in "
        "out of key converted singing?"
    )
    quote = (
        "However, the converted singing voice can be easily out of key, showing "
        "that the existing approach can not model the pitch information precisely."
    )

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("pitch", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["verdict"] == "insufficient_evidence"
    assert result.trace["reason"] == "other_than_alternative_unproven"
    assert "authoritative_quote_evidence_id" not in result.trace
    assert "grounded_complete_proposition" not in result.trace["reason"]


def test_other_than_yes_binds_the_independent_alternative_span() -> None:
    question = (
        "Do they experiment with their proposed model on any other dataset "
        "other than MovieQA?"
    )
    movieqa = _item(
        "movieqa",
        "We mainly focus on the MovieQA dataset to train and evaluate our model.",
    )
    mctest_quote = "We tested the proposed model on the MCTest dataset."
    mctest = _item("mctest", mctest_quote)

    result = verify_qasper_answerability(
        _Verifier("yes_complete", mctest_quote),
        question=question,
        answer_type="boolean",
        evidence=f"{movieqa['text']} {mctest_quote}",
        evidence_items=[movieqa, mctest],
        candidate_answer="no",
    )

    assert result.answer == "yes"
    assert result.trace["action"] == "corrected_polarity"
    assert result.trace["authoritative_quote_evidence_id"] == ("evidence:paper:mctest")
    assert (
        result.trace["authoritative_quote_span_id"]
        == canonical_quote_spans(
            mctest,
            mctest_quote,
            text=mctest_quote,
        )[0].identity
    )
    assert result.trace["final_support_evidence_ids"] == ["evidence:paper:mctest"]


def test_other_than_no_requires_and_accepts_explicit_exclusivity() -> None:
    question = (
        "Do they experiment with their proposed model on any other dataset "
        "other than MovieQA?"
    )
    quote = (
        "We evaluated the proposed model only on the MovieQA dataset and no "
        "other dataset."
    )

    result = verify_qasper_answerability(
        _Verifier("no_complete", quote),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("exclusive-movieqa", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "no"
    assert result.trace["action"] == "corrected_polarity"
    assert result.trace["authoritative_quote_evidence_id"] == (
        "evidence:paper:exclusive-movieqa"
    )


def test_quality_control_exception_preserves_exact_authority_identity() -> None:
    question = "Are the automatically constructed datasets subject to quality control?"
    quote = (
        "While we are able to generate large amounts of systematically controlled "
        "data at virtually no cost or need for manual annotation, it is much "
        "harder to validate the quality of such data at such a scale and such "
        "varying levels of complexity."
    )

    result = verify_qasper_answerability(
        _Verifier("no_complete", quote),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("quality", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "no"
    assert result.trace["action"] == "corrected_polarity"
    assert result.trace["authoritative_quote_evidence_id"] == ("evidence:paper:quality")
    assert (
        result.trace["authoritative_quote_span_id"]
        == canonical_quote_spans(
            _item("quality", quote),
            quote,
            text=quote,
        )[0].identity
    )
    assert result.trace["final_support_evidence_ids"] == ["evidence:paper:quality"]


@pytest.mark.parametrize(
    ("question", "quote", "candidate", "verdict", "expected"),
    (
        (
            "Did the authors release the code?",
            "The authors did not release the code with the paper.",
            "yes",
            "no_complete",
            "no",
        ),
        (
            "Is pre-training effective in their evaluation?",
            (
                "The encoder-decoder-reconstructor can not be trained well without "
                "pre-training, so it proves that we have to train the forward "
                "translation model as pre-training."
            ),
            "no",
            "yes_complete",
            "yes",
        ),
        (
            "Does RoBERTa outperform BERT?",
            "We also observe that XLNet consistently outperforms BERT and RoBERTa.",
            "yes",
            "no_complete",
            "no",
        ),
    ),
)
def test_existing_high_precision_semantic_corrections_remain_authoritative(
    question: str,
    quote: str,
    candidate: str,
    verdict: str,
    expected: str,
) -> None:
    result = verify_qasper_answerability(
        _Verifier(verdict, quote),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("semantic", quote)],
        candidate_answer=candidate,
    )

    assert result.answer == expected
    assert result.trace["action"] == "corrected_polarity"
    assert result.trace["authoritative_quote_evidence_id"] == (
        "evidence:paper:semantic"
    )


def test_rejected_authority_clears_terminal_support_and_citation_state() -> None:
    question = "Do they experiment with the toolkits?"
    quote = (
        "We present GluonCV and GluonNLP, the deep learning toolkits for computer "
        "vision and natural language processing based on Apache MXNet "
        "(incubating)."
    )
    evidence = _item("toolkits", quote)
    prediction: dict[str, Any] = {
        "question": question,
        "answer_type": "boolean",
        "predicted_answer": "yes",
        "route": "text_rag",
        "gold_evidence": ["anonymous-support"],
        "evidence_bundle": {"items": [evidence], "metadata": {}},
        "evidence_metadata": {
            "selected_evidence": [evidence],
            "generation_context_evidence": [evidence],
        },
        "structured_citations": [],
        "predicted_citations": [],
    }
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_typed",
        mode="scoring_adapter_v1",
    )

    applied = apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: _Verifier("no_complete", quote),
    )
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_typed",
        mode="scoring_adapter_v1",
    )
    synchronized = synchronize_terminal_answer_state(prediction)

    trace = prediction["evidence_metadata"]["qasper_answerability"]
    assert applied is True
    assert synchronized is True
    assert prediction["answer_for_scoring"] == "unanswerable"
    assert prediction["terminal_answer_state"]["answer"] == "unanswerable"
    assert trace["reason"] == "polarity_authority_unproven"
    assert "authoritative_quote_evidence_id" not in trace
    assert prediction["evidence_metadata"]["verified_claim_support_evidence"] == []
    assert prediction["structured_citations"] == []
    assert prediction["terminal_answer_state"]["supporting_evidence"] == []
    assert prediction["terminal_answer_state"]["emitted_citations"] == []
    assert (
        contract_invariant_summary([prediction])["qasper_stale_verifier_state_count"]
        == 0.0
    )
    assert not (
        trace["reason"] == "grounded_complete_proposition"
        and prediction["answer_for_scoring"] == "unanswerable"
    )
