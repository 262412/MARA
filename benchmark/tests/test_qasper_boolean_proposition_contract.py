from __future__ import annotations

from typing import Any

from ktem.docqa.boolean_evidence_scope import (
    classify_boolean_evidence,
    classify_boolean_evidence_set,
)

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.qasper_answerability import verify_qasper_answerability
from benchmark.qasper_contract_invariants import qasper_contract_metric_values
from benchmark.qasper_prompt_budget import fit_qasper_verifier_items
from benchmark.qasper_proposition_conflict import resolve_boolean_conflict
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


def test_boolean_verifier_packs_quote_scoped_snippet_with_lineage():
    decisive = (
        "We do not release the training data because the source license forbids it."
    )
    long_item = _item(
        "release-policy",
        ("Unrelated background sentence. " * 500) + decisive,
    )

    _prompt, bounded, trace = fit_qasper_verifier_items(
        [long_item],
        lambda evidence: f"QUESTION\n{evidence}",
        question="Did the authors release the training data?",
        candidate_answer="no",
        required_evidence_ids=["evidence:paper:release-policy"],
        required_slot_ids=["support:boolean_proposition"],
    )

    assert decisive in bounded
    assert "span_start=" in bounded
    assert "span_end=" in bounded
    assert len(bounded) < 1500
    assert trace["verifier_required_evidence_coverage"] == "1.000000"
    assert trace["verifier_required_slot_ids"] == "support:boolean_proposition"


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


def test_current_paper_experiment_not_confused_with_other_authors() -> None:
    item = _item(
        "other-authors",
        "Smith et al. evaluated the model on clinical tasks.",
        section="results",
    )

    assessment = classify_boolean_evidence(
        "Did the authors evaluate the model on clinical tasks?",
        "yes",
        item,
    )

    assert assessment.classification == "insufficient_scope"
    assert assessment.proposition.actor == "other_authors"


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


def test_unrelated_negation_does_not_flip_target_predicate() -> None:
    item = _item(
        "mixed",
        (
            "We did not release the source code, but we evaluated the model "
            "on clinical tasks."
        ),
    )

    assessment = classify_boolean_evidence(
        "Did the authors evaluate the model on clinical tasks?",
        "yes",
        item,
    )

    assert assessment.classification == "supports"
    assert assessment.proposition.polarity == "yes"


def test_negation_of_other_relation_does_not_flip_target_predicate() -> None:
    item = _item(
        "mixed-relations",
        (
            "We did not train the model on clinical tasks; "
            "we evaluated it on clinical tasks."
        ),
    )

    assessment = classify_boolean_evidence(
        "Did the authors evaluate the model on clinical tasks?",
        "yes",
        item,
    )

    assert assessment.classification == "supports"
    assert assessment.proposition.action == "evaluate"


def test_proposition_key_contains_identity_and_polarity_dimensions() -> None:
    assessment = classify_boolean_evidence(
        "Did the authors evaluate the model on clinical tasks?",
        "yes",
        _item("support", "We evaluated the model on clinical tasks."),
    )

    assert assessment.proposition.key == (
        "current_paper",
        "evaluate",
        "clinical model task",
        "results",
        "none",
        "yes",
    )


def test_boolean_recovery_requires_claim_specific_support_identity() -> None:
    quote = "We evaluated the model on clinical tasks."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote),
        question="Did the authors evaluate the model on clinical tasks?",
        evidence=quote,
        evidence_items=[],
        candidate_answer="unanswerable",
    )

    assert result.answer == "unanswerable"
    assert result.trace["action"] == "preserved_boolean_abstention"


def test_weak_candidate_support_is_not_preserved() -> None:
    action, answer, trace = resolve_boolean_conflict(
        "We evaluated a benchmark.",
        "Did the authors evaluate the model on clinical tasks?",
        candidate_polarity="yes",
        verdict="insufficient_evidence",
    )

    assert action == "abstained_insufficient_evidence"
    assert answer == "unanswerable"
    assert trace["conflict_status"] == "insufficient_evidence"


def test_authoritative_same_polarity_quote_confirms_candidate_without_chunk_score():
    action, answer, trace = resolve_boolean_conflict(
        "",
        "Did the authors release the code?",
        candidate_polarity="yes",
        verdict="yes",
        evidence_items=[],
        authoritative_claim_key=("current_paper", "release", "code"),
        authoritative_polarity="yes",
    )

    assert action == "confirmed_candidate"
    assert answer == "yes"
    assert trace["verdict_support_score"] == "1.000"


def test_exact_positive_support_beats_unrelated_negative_clause() -> None:
    positive = _item(
        "positive",
        "We evaluated the model on clinical tasks and report the results.",
    )
    unrelated_negative = _item(
        "negative",
        "We did not release the implementation used for the experiments.",
    )

    classified = classify_boolean_evidence_set(
        "Did the authors evaluate the model on clinical tasks?",
        "yes",
        [unrelated_negative, positive],
    )

    assert [value.item["evidence_id"] for value in classified.supports] == ["positive"]
    assert classified.contradicts == ()


def test_balanced_conflict_requires_the_same_proposition_key() -> None:
    positive = _item(
        "positive",
        "We evaluated the model on clinical tasks.",
    )
    negative = _item(
        "negative",
        "We did not evaluate the model on clinical tasks.",
    )

    action, answer, trace = resolve_boolean_conflict(
        "",
        "Did the authors evaluate the model on clinical tasks?",
        candidate_polarity="yes",
        verdict="no",
        evidence_items=[positive, negative],
    )

    assert action == "abstained_polarity_conflict"
    assert answer == "unanswerable"
    assert trace["conflict_status"] == "balanced_conflict"


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


def test_language_identity_is_not_collapsed_for_non_quantified_claim() -> None:
    assessment = classify_boolean_evidence(
        "Did the authors evaluate German datasets?",
        "yes",
        _item("greek", "We evaluated Greek datasets in our experiments."),
    )

    assert assessment.classification == "unrelated"
    assert "german" in assessment.proposition.object


def test_insufficient_verdict_cannot_preserve_candidate_from_broad_chunk_score() -> None:
    positive = _item("positive", "We evaluated German datasets.")

    action, answer, trace = resolve_boolean_conflict(
        "",
        "Did the authors evaluate German datasets?",
        candidate_polarity="yes",
        verdict="insufficient_evidence",
        evidence_items=[positive],
    )

    assert action == "abstained_insufficient_evidence"
    assert answer == "unanswerable"
    assert trace["conflict_status"] == "insufficient_evidence"


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


def test_grounded_complete_no_is_authoritative_for_its_exact_evidence_identity() -> None:
    quote = (
        "While we can generate systematically controlled data without manual "
        "annotation, it is much harder to validate the quality of such data."
    )
    item = _item(
        "quality-control",
        (
            "The paper discusses synthetic challenge datasets at length. "
            f"{quote} Additional discussion covers model robustness."
        ),
    )

    result = verify_qasper_answerability(
        _Verifier("no_complete", quote),
        question="Are the automatically constructed datasets subject to quality control?",
        evidence=item["text"],
        evidence_items=[item],
        candidate_answer="unanswerable",
    )

    assert result.answer == "no"
    assert result.trace["reason"] == "grounded_complete_proposition"
    assert result.trace["authoritative_quote_evidence_id"] == (
        "evidence:paper:quality-control"
    )
    assert result.trace["final_support_evidence_ids"] == [
        "evidence:paper:quality-control"
    ]


def test_grounded_complete_quote_still_abstains_on_same_proposition_conflict() -> None:
    quote = "We evaluated the model on clinical tasks."
    support = _item("support", quote)
    contradiction = _item(
        "contradiction",
        "We did not evaluate the model on clinical tasks.",
    )

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote),
        question="Did the authors evaluate the model on clinical tasks?",
        evidence=f"{quote} {contradiction['text']}",
        evidence_items=[support, contradiction],
        candidate_answer="unanswerable",
    )

    assert result.answer == "unanswerable"
    assert result.trace["conflict_status"] == "balanced_conflict"


def test_grounded_complete_quote_without_unique_evidence_identity_is_rejected() -> None:
    quote = "We evaluated the model on clinical tasks."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote),
        question="Did the authors evaluate the model on clinical tasks?",
        evidence=f"{quote}\n\n{quote}",
        evidence_items=[_item("first", quote), _item("second", quote)],
        candidate_answer="unanswerable",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "quote_identity_unresolved"


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
    assert prediction["predicted_evidence"] == [evidence["text"]]
    assert prediction["evidence_metadata"]["emitted_citation_evidence"] == [evidence]
    metrics = qasper_contract_metric_values(
        prediction,
        prediction["evidence_metadata"],
        cited=prediction["evidence_metadata"]["emitted_citation_evidence"],
        contract_items=[evidence],
    )
    assert metrics["citation_scope_violation_count"] == 0.0
    assert (
        contract_invariant_summary([prediction])["qasper_stale_verifier_state_count"]
        == 0.0
    )
    assert prediction["evidence_metadata"]["qasper_answerability"][
        "evidence_quote"
    ].startswith("In fact, I have been unable")


def test_authoritative_quality_quote_identity_survives_terminal_rebinding() -> None:
    quote = (
        "It is much harder to validate the quality of such data at such a "
        "scale and such varying levels of complexity."
    )
    evidence = _item("quality", quote)
    prediction: dict[str, Any] = {
        "question": (
            "Are the automatically constructed datasets subject to quality control?"
        ),
        "answer_type": "boolean",
        "predicted_answer": "yes",
        "route": "text_only",
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

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: _Verifier("no_complete", quote),
    )
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_typed",
        mode="scoring_adapter_v1",
    )
    synchronize_terminal_answer_state(prediction)

    trace = prediction["evidence_metadata"]["qasper_answerability"]
    assert prediction["answer_for_scoring"] == "no"
    assert trace["authoritative_quote_evidence_id"] == "evidence:paper:quality"
    assert prediction["evidence_metadata"]["verified_claim_support_evidence"] == [
        evidence
    ]
    assert prediction["predicted_evidence"] == [quote]
    assert prediction["structured_citations"][0]["evidence_id"] == (
        "evidence:paper:quality"
    )


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
