from __future__ import annotations

import json
from typing import Any

import pytest

from benchmark.qasper_answerability import verify_qasper_answerability


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


def test_two_object_quantifier_rejects_quote_proving_only_one_dataset() -> None:
    question = "Did they collect the two datasets?"
    quote = "The CreateDebate dataset was collected from createDebate.com."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("create-debate", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["verdict"] == "insufficient_evidence"
    assert result.trace["reason"] == "quantified_object_scope_incomplete"
    assert result.trace.get("evidence_ref", "") == ""
    assert result.trace.get("evidence_quote", "") == ""


def test_two_object_quantifier_accepts_both_named_datasets_for_same_relation() -> None:
    question = "Did they collect the two datasets?"
    quote = "We collected the FBFans and CreateDebate datasets."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("both-datasets", quote)],
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert result.trace["boolean_scope_reason"] == "quantified_object_scope_complete"


def test_two_object_quantifier_rejects_unrelated_count_in_same_quote() -> None:
    question = "Did they collect the two datasets?"
    quote = "We used two classifiers and collected the CreateDebate dataset."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("unrelated-count", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "quantified_object_scope_incomplete"


def test_named_both_quantifier_requires_and_accepts_each_named_object() -> None:
    question = "Did they evaluate both Dataset A and Dataset B?"
    quote = "We evaluated Dataset A and Dataset B."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("named-pair", quote)],
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert result.trace["boolean_scope_reason"] == "quantified_object_scope_complete"


def test_all_quantifier_rejects_all_applied_to_an_unrelated_object() -> None:
    question = "Did they evaluate all datasets?"
    quote = "We evaluated all models, but one dataset was described in the appendix."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("wrong-all-object", quote)],
        candidate_answer="unanswerable",
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
