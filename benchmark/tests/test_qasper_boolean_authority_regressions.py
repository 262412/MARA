from __future__ import annotations

from typing import Any

import pytest

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.qasper_answerability import verify_qasper_answerability
from benchmark.qasper_evidence_identity import canonical_quote_spans
from benchmark.task_answer_contracts import (
    apply_task_answer_contract,
    synchronize_terminal_answer_state,
)
from benchmark.tests.qasper_test_support import BooleanVerifier as _Verifier


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


def test_verifier_ref_is_rebound_when_quote_has_one_canonical_prompt_span() -> None:
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

    assert result.answer == "yes"
    assert result.trace["reason"] == "grounded_complete_proposition"
    assert result.trace["evidence_ref"] == "E1:S1"
    assert result.trace["evidence_ref_rebound"] == "true"
    assert result.trace["authoritative_quote_evidence_id"] == "evidence:paper:support"


def test_verifier_ref_mismatch_is_rejected_when_quote_occurs_more_than_once() -> None:
    quote = "We evaluated the model on clinical tasks."
    repeated = _item("repeated", f"{quote} {quote}")
    distractor = _item("distractor", "The appendix lists training parameters.")

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E2:S1", "E1:S1"),
        question="Did the authors evaluate the model on clinical tasks?",
        answer_type="boolean",
        evidence=f"{repeated['text']} {distractor['text']}",
        evidence_items=[repeated, distractor],
        candidate_answer="unanswerable",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "evidence_ref_quote_mismatch"
    assert result.trace.get("evidence_ref", "") == ""
    assert result.trace.get("evidence_quote", "") == ""


def test_all_quantifier_rejects_all_applied_to_an_unrelated_object() -> None:
    question = "Did they evaluate all datasets?"
    quote = "We evaluated all models, but one dataset was described in the appendix."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("wrong-all-object", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "quantified_object_scope_incomplete"


@pytest.mark.parametrize("marker", ("every", "each"))
def test_every_and_each_use_closed_all_scope(marker: str) -> None:
    question = f"Did they evaluate {marker} dataset?"
    quote = f"We evaluated {marker} dataset."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("all-synonym", quote)],
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert result.trace["boolean_quantifier"] == "all"
    assert result.trace["boolean_scope_reason"] == "quantified_object_scope_complete"


def test_all_with_explicit_count_uses_closed_object_scope() -> None:
    question = "Did they evaluate all 3 datasets?"
    quote = "We evaluated all 3 datasets."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("all-explicit-count", quote)],
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert result.trace["boolean_quantifier"] == "all"
    assert result.trace["boolean_scope_reason"] == "quantified_object_scope_complete"


@pytest.mark.parametrize("marker", ("every", "each"))
def test_every_and_each_reject_explicit_exceptions(marker: str) -> None:
    question = f"Did they evaluate {marker} dataset?"
    quote = f"We evaluated {marker} dataset except one."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("all-synonym-exception", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "quantified_object_scope_incomplete"


@pytest.mark.parametrize(
    "quote",
    (
        "We evaluated all models and one dataset.",
        "We evaluated every model, including one dataset.",
    ),
)
def test_all_quantifier_does_not_float_across_a_mixed_object_clause(quote: str) -> None:
    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question="Did they evaluate all datasets?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("floating-all", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "quantified_object_scope_incomplete"


def test_only_quantifier_does_not_float_across_a_mixed_object_clause() -> None:
    quote = "We evaluated only models and one dataset."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question="Did they evaluate only datasets?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("floating-only", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "quantified_object_scope_incomplete"


@pytest.mark.parametrize(
    "quote",
    (
        "We evaluated only datasets, but also models.",
        "We evaluated only datasets, but we also evaluated models.",
        "We evaluated only datasets and we evaluated models.",
        "We evaluated only datasets and one model.",
        "Only datasets and one model were evaluated.",
        "Only datasets and models were evaluated.",
        "We evaluated only datasets, with models as well.",
        "We evaluated only datasets, except models.",
    ),
)
def test_only_quantifier_rejects_additional_target_objects(quote: str) -> None:
    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question="Did they evaluate only datasets?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("only-extra-object", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "quantified_object_scope_incomplete"


@pytest.mark.parametrize(
    "quote",
    (
        "We evaluated all datasets, but did not evaluate one dataset.",
        "We evaluated all datasets; however, one dataset was not evaluated.",
        "We evaluated all datasets, whereas one dataset was omitted.",
        "We evaluated all datasets except one.",
        "All datasets except one were evaluated.",
        "We evaluated all datasets, but one was omitted.",
    ),
)
def test_all_quantifier_rejects_explicit_target_object_exceptions(quote: str) -> None:
    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question="Did they evaluate all datasets?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("all-object-exception", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "quantified_object_scope_incomplete"


def test_only_quantifier_accepts_explicit_exclusion_of_other_objects() -> None:
    quote = "We evaluated only datasets, no models."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question="Did they evaluate only datasets?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("only-explicit-exclusion", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "yes"
    assert result.trace["boolean_scope_reason"] == "quantified_object_scope_complete"


def test_count_quantifier_rejects_another_papers_complete_count() -> None:
    question = "Did they collect the two datasets?"
    quote = "Another paper collected both datasets."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("third-party-count", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "cited_work_does_not_establish_current_paper_claim"


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


def test_missing_runtime_authority_is_audited_without_reanswering() -> None:
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
    assert applied is False
    assert synchronized is True
    assert prediction["answer_for_scoring"] == "yes"
    assert prediction["contract_action"] == ("hard_violation_missing_runtime_authority")
    assert trace["reason"] == "runtime_projection_missing"
    assert trace["authoritative_quote_evidence_id"] == ""
    assert prediction["structured_citations"] == []
    assert prediction["post_engine_answerability_llm_call_count"] == 0
