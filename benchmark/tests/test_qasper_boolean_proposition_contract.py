from __future__ import annotations

from typing import Any

from ktem.docqa.boolean_evidence_scope import (
    classify_boolean_evidence,
    classify_boolean_evidence_set,
)

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.qasper_answerability import verify_qasper_answerability
from benchmark.qasper_contract_invariants import qasper_contract_metric_values
from benchmark.task_answer_contracts import (
    apply_task_answer_contract,
    synchronize_terminal_answer_state,
)


class _Verifier:
    def __init__(self, verdict: str, quote: str) -> None:
        self.verdict = verdict
        self.quote = quote

    def __call__(self, _prompt: str, **_kwargs: Any) -> Any:
        return type(
            "Result",
            (),
            {"text": f'{{"verdict":"{self.verdict}","evidence_quote":"{self.quote}"}}'},
        )()


def _item(
    evidence_id: str,
    text: str,
    *,
    section: str = "results",
) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": section,
        "text": text,
    }


def test_unrelated_relation_is_not_contradiction() -> None:
    item = _item("code", "We release the implementation and documentation.")

    assessment = classify_boolean_evidence(
        "Did the authors evaluate the model on clinical tasks?",
        "yes",
        item,
    )

    assert assessment.classification == "unrelated"
    assert assessment.proposition.action == "provide"


def test_current_paper_experiment_not_confused_with_related_work() -> None:
    item = _item(
        "related",
        "Previous work evaluated the model on clinical tasks.",
        section="related_work",
    )

    assessment = classify_boolean_evidence(
        "Did the authors evaluate the model on clinical tasks?",
        "yes",
        item,
    )

    assert assessment.classification == "insufficient_scope"
    assert assessment.proposition.actor == "cited_work"


def test_future_work_does_not_prove_experiment_was_performed() -> None:
    item = _item(
        "future",
        "In future work, we will evaluate the model on clinical tasks.",
        section="future_work",
    )

    assessment = classify_boolean_evidence(
        "Did the authors evaluate the model on clinical tasks?",
        "yes",
        item,
    )

    assert assessment.classification == "insufficient_scope"


def test_valid_relation_paraphrase_is_not_filtered() -> None:
    item = _item(
        "support",
        "Our assistant was built with packaged NLP components.",
        section="methods",
    )

    assessment = classify_boolean_evidence(
        "Do they use off-the-shelf NLP systems to build their assistant?",
        "yes",
        item,
    )

    assert assessment.classification == "supports"
    assert assessment.relation_score > 0


def test_high_confidence_support_survives_unrelated_evidence() -> None:
    support = _item(
        "support",
        "We evaluated the model on clinical tasks and report the results.",
    )
    unrelated = _item("unrelated", "We did not release the source code.")

    classified = classify_boolean_evidence_set(
        "Did the authors evaluate the model on clinical tasks?",
        "yes",
        [unrelated, support],
    )

    assert [item.item["evidence_id"] for item in classified.supports] == ["support"]
    assert classified.contradicts == ()


def test_only_quantifier_requires_scope_valid_counterexample() -> None:
    related = _item(
        "related",
        "Previous work evaluated a Greek dataset.",
        section="related_work",
    )
    current = _item(
        "current",
        "We additionally evaluate a German dataset in our experiments.",
        section="experiments",
    )

    classified = classify_boolean_evidence_set(
        "Do they evaluate only on English datasets?",
        "yes",
        [related, current],
    )

    assert [item.item["evidence_id"] for item in classified.contradicts] == ["current"]
    assert classified.insufficient_scope[0].item["evidence_id"] == "related"


def test_supported_boolean_answer_is_not_false_abstained() -> None:
    quote = "We evaluated the model on clinical tasks and report the results."
    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote),
        question="Did the authors evaluate the model on clinical tasks?",
        evidence=quote,
        evidence_items=[_item("support", quote)],
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"


def test_deterministic_experiment_resolution_keeps_its_selected_evidence() -> None:
    quote = (
        "For instance, the sentence is translated by Google Translate, Bing "
        "Translate, and Yandex. In fact, I have been unable to construct any "
        "English sentence that those systems translate using the feminine "
        "plural pronoun."
    )
    result = verify_qasper_answerability(
        _Verifier("insufficient_evidence", ""),
        question="Do the authors conduct experiments on the tasks mentioned?",
        evidence=quote,
        evidence_items=[_item("experiment", quote)],
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert result.trace["verifier_input_evidence_ids"] == ("evidence:paper:experiment")


def test_deterministic_experiment_support_survives_terminal_citation_rebuild() -> None:
    evidence = _item(
        "experiment",
        (
            "This paper discusses how sentence pairs could be used as "
            "challenges for machine translation. For instance, the sentence "
            "is translated by Google Translate, Bing Translate, and Yandex. "
            "In fact, I have been unable to construct any English sentence "
            "that those systems translate using the feminine plural pronoun."
        ),
    )
    prediction: dict[str, Any] = {
        "question": "Do the authors conduct experiments on the tasks mentioned?",
        "answer_type": "boolean",
        "predicted_answer": "unanswerable",
        "route": "hybrid",
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
        llm_factory=lambda: _Verifier("insufficient_evidence", ""),
    )
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_typed",
        mode="scoring_adapter_v1",
    )
    synchronized = synchronize_terminal_answer_state(prediction)

    assert applied is True
    assert synchronized is True
    assert prediction["answer_for_scoring"] == "yes"
    assert prediction["verify_decision"]["status"] == "supported"
    assert prediction["structured_citations"]
    assert prediction["evidence_metadata"]["verified_claim_support_evidence"] == [
        evidence
    ]
    assert prediction["evidence_metadata"]["emitted_citation_evidence"] == [evidence]
    metrics = qasper_contract_metric_values(
        prediction,
        prediction["evidence_metadata"],
        cited=prediction["evidence_metadata"]["emitted_citation_evidence"],
        contract_items=[evidence],
    )
    assert metrics["citation_scope_violation_count"] == 0.0
    assert prediction["evidence_metadata"]["qasper_answerability"][
        "evidence_quote"
    ].startswith("In fact, I have been unable")


def test_wrong_polarity_is_rejected_without_abstaining_valid_answer() -> None:
    quote = "We evaluated the model on clinical tasks and report the results."
    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote),
        question="Did the authors evaluate the model on clinical tasks?",
        evidence=quote,
        evidence_items=[_item("support", quote)],
        candidate_answer="no",
    )

    assert result.answer == "yes"
    assert result.trace["action"] == "corrected_polarity"
