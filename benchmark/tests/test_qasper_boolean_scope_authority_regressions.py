from __future__ import annotations

import json
from typing import Any

import pytest

from benchmark.qasper_answerability import verify_qasper_answerability
from benchmark.qasper_contract_invariants import qasper_contract_metric_values
from benchmark.qasper_evidence_priorities import qasper_evidence_priorities
from benchmark.qasper_prompt_budget import (
    _boolean_proposition_snippet,
    fit_qasper_verifier_items,
)


class _Verifier:
    def __init__(self, verdict: str, quote: str, evidence_ref: str = "") -> None:
        self.calls = 0
        self.response = json.dumps(
            {
                "verdict": verdict,
                "evidence_ref": evidence_ref,
                "evidence_quote": quote,
            },
            ensure_ascii=False,
        )

    def __call__(self, _prompt: str, **_kwargs: Any) -> Any:
        self.calls += 1
        return type("Result", (), {"text": self.response})()


def _item(evidence_id: str, text: str) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "results",
        "text": text,
    }


def test_required_verification_slot_without_references_remains_visible_as_missing_authority() -> None:
    prediction = {
        "evidence_metadata": {
            "query_plan": {
                "evidence_slots": [
                    {
                        "slot_id": "support:boolean_proposition",
                        "required_for_verification": True,
                        "evidence_ids": [],
                    }
                ]
            }
        }
    }

    priorities = qasper_evidence_priorities(
        prediction,
        [_item("support", "The authors evaluate the model.")],
        question="Did the authors evaluate the model?",
        candidate_answer="yes",
    )

    assert priorities.required_evidence_ids == ()
    assert priorities.required_slot_ids == ("support:boolean_proposition",)
    assert priorities.missing_required_slot_ids == ("support:boolean_proposition",)


def test_empty_required_authority_is_not_full_verifier_coverage() -> None:
    _prompt, _bounded, trace = fit_qasper_verifier_items(
        [_item("support", "The authors evaluate the model.")],
        lambda evidence: f"QUESTION\n{evidence}",
        question="Did the authors evaluate the model?",
        candidate_answer="yes",
        required_evidence_ids=[],
        required_slot_ids=["support:boolean_proposition"],
    )

    assert trace["verifier_required_evidence_coverage"] == "0.000000"
    assert trace["verifier_required_authority_status"] == "missing_required_evidence"
    assert trace["verifier_required_slot_authority_count"] == "0"


def test_required_reference_and_prompt_quote_share_canonical_lineage() -> None:
    item = _item("support", "The authors evaluate the model on clinical tasks.")
    item["span_id"] = "support"
    prediction = {
        "evidence_metadata": {
            "query_plan": {
                "evidence_slots": [
                    {
                        "slot_id": "support:boolean_proposition",
                        "required_for_verification": True,
                        "evidence_ids": ["span:paper:support"],
                    }
                ]
            }
        }
    }

    priorities = qasper_evidence_priorities(
        prediction,
        [item],
        question="Did the authors evaluate the model on clinical tasks?",
        candidate_answer="yes",
    )
    _prompt, _bounded, trace = fit_qasper_verifier_items(
        [item],
        lambda evidence: f"QUESTION\n{evidence}",
        question="Did the authors evaluate the model on clinical tasks?",
        candidate_answer="yes",
        required_evidence_ids=list(priorities.required_evidence_ids),
        required_slot_ids=list(priorities.required_slot_ids),
    )

    assert priorities.required_evidence_ids == ("span:paper:support",)
    assert trace["verifier_required_evidence_coverage"] == "1.000000"
    assert trace["verifier_input_evidence_ids"] == "span:paper:support"
    assert (
        '"runtime_evidence_id":"span:paper:support"'
        in trace["verifier_evidence_alias_mapping"]
    )


def test_partial_required_slot_authority_cannot_report_full_coverage() -> None:
    first = _item("first", "The authors evaluate the model on clinical tasks.")
    first["span_id"] = "first"
    prediction = {
        "evidence_metadata": {
            "query_plan": {
                "evidence_slots": [
                    {
                        "slot_id": "support:clinical",
                        "required_for_verification": True,
                        "evidence_ids": ["span:paper:first"],
                    },
                    {
                        "slot_id": "support:missing",
                        "required_for_verification": True,
                        "evidence_ids": [],
                    },
                ]
            }
        }
    }

    priorities = qasper_evidence_priorities(
        prediction,
        [first],
        question="Did the authors evaluate the model on clinical tasks?",
        candidate_answer="yes",
    )
    _prompt, _bounded, trace = fit_qasper_verifier_items(
        [first],
        lambda evidence: f"QUESTION\n{evidence}",
        question="Did the authors evaluate the model on clinical tasks?",
        candidate_answer="yes",
        required_evidence_ids=list(priorities.required_evidence_ids),
        required_slot_ids=list(priorities.required_slot_ids),
        missing_required_slot_ids=list(priorities.missing_required_slot_ids),
        missing_required_evidence_ids=list(priorities.missing_required_evidence_ids),
    )

    assert priorities.required_slot_ids == (
        "support:clinical",
        "support:missing",
    )
    assert priorities.missing_required_slot_ids == ("support:missing",)
    assert trace["verifier_required_evidence_coverage"] == "0.000000"
    assert trace["verifier_required_slot_authority_count"] == "1"
    assert trace["verifier_required_authority_status"] == "missing_required_evidence"


def test_unresolved_required_reference_marks_its_slot_missing() -> None:
    item = _item("support", "The authors evaluate the model on clinical tasks.")
    prediction = {
        "evidence_metadata": {
            "query_plan": {
                "evidence_slots": [
                    {
                        "slot_id": "support:boolean_proposition",
                        "required_for_verification": True,
                        "evidence_ids": ["span:paper:not-selected"],
                    }
                ]
            }
        }
    }

    priorities = qasper_evidence_priorities(
        prediction,
        [item],
        question="Did the authors evaluate the model on clinical tasks?",
        candidate_answer="yes",
    )

    assert priorities.required_evidence_ids == ()
    assert priorities.missing_required_slot_ids == ("support:boolean_proposition",)
    assert priorities.missing_required_evidence_ids == ("span:paper:not-selected",)


def test_quality_control_prompt_snippet_keeps_quality_validation_sentence() -> None:
    text = (
        "We find automatically constructing probes to be vulnerable to annotation "
        "artifacts, which we carefully control for. It is much harder to validate "
        "the quality of such data at such a scale and such varying levels of "
        "complexity."
    )

    snippets, _spans = _boolean_proposition_snippet(
        text,
        "Are the automatically constructed datasets subject to quality control?",
    )

    assert any("validate the quality" in snippet for snippet in snippets)


def test_quality_validation_quote_remains_grounded_no() -> None:
    quote = (
        "It is much harder to validate the quality of such data at such a scale "
        "and such varying levels of complexity."
    )
    result = verify_qasper_answerability(
        _Verifier("no_complete", quote, "E1:S1"),
        question="Are the automatically constructed datasets subject to quality control?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("quality-validation", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "no"
    assert result.trace["reason"] == "grounded_complete_proposition"
    assert result.trace["evidence_ref"] == "E1:S1"
    assert result.trace["evidence_quote"] == quote


def test_free_text_missing_required_authority_abstains_before_verifier_call() -> None:
    verifier = _Verifier(
        "supported",
        "The authors evaluate the model on clinical tasks.",
        "E1:S1",
    )
    result = verify_qasper_answerability(
        verifier,
        question="What did the authors evaluate?",
        answer_type="free_text",
        evidence="The authors evaluate the model on clinical tasks.",
        evidence_items=[
            _item("support", "The authors evaluate the model on clinical tasks.")
        ],
        required_evidence_ids=[],
        required_slot_ids=["support:boolean_proposition"],
        candidate_answer="the model on clinical tasks",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "missing_required_evidence_authority"
    assert result.trace["action"] == "abstained_missing_required_evidence"
    assert verifier.calls == 0


def test_complete_verdict_with_empty_required_authority_is_cleared_safely() -> None:
    quote = "The authors evaluate the model on clinical tasks."
    verifier = _Verifier("yes_complete", quote, "E1:S1")
    result = verify_qasper_answerability(
        verifier,
        question="Did the authors evaluate the model on clinical tasks?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("support", quote)],
        required_evidence_ids=[],
        required_slot_ids=["support:boolean_proposition"],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "missing_required_evidence_authority"
    assert result.trace["verdict"] == "insufficient_evidence"
    assert result.trace.get("evidence_ref", "") == ""
    assert result.trace.get("evidence_quote", "") == ""
    assert verifier.calls == 0


def test_empty_authority_abstention_does_not_count_as_complete_verdict_cleanup() -> None:
    quote = "The authors evaluate the model on clinical tasks."
    verifier = _Verifier("yes_complete", quote, "E1:S1")
    result = verify_qasper_answerability(
        verifier,
        question="Did the authors evaluate the model on clinical tasks?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("support", quote)],
        required_evidence_ids=[],
        required_slot_ids=["support:boolean_proposition"],
        candidate_answer="yes",
    )
    prediction: dict[str, Any] = {
        "answer_type": "boolean",
        "predicted_answer": result.answer,
        "gold_answers": ["yes"],
        "evidence_metadata": {"qasper_answerability": result.trace},
    }

    metrics = qasper_contract_metric_values(
        prediction,
        prediction["evidence_metadata"],
        cited=[],
        contract_items=[_item("support", quote)],
    )

    assert metrics["qasper_required_slot_authority_empty_count"] == 1.0
    assert metrics["qasper_complete_to_unanswerable_empty_authority_count"] == 0.0


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
    assert result.trace["evidence_ref"] == "E1:S1"
    assert result.trace["evidence_quote"] == quote
    assert result.trace["boolean_scope_reason"] == "quantified_object_scope_incomplete"


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
    assert result.trace["evidence_ref"] == "E1:S1"
    assert result.trace["evidence_quote"] == quote
    assert result.trace["boolean_scope_reason"] == "quantified_object_scope_incomplete"


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
