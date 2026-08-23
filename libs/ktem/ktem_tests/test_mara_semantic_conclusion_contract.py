from __future__ import annotations

from typing import Any

from ktem.docqa.conclusion_audit import (
    ConclusionAudit,
    conclusion_audit_attestation,
    conclusion_audit_validation_reason,
)
from ktem.docqa.polarity_contradiction_check import polarity_contradiction_check
from ktem.docqa.question_proposition import (
    QuestionProposition,
    TypedConclusion,
    build_question_proposition,
    question_proposition_completeness_reason,
    resolve_question_proposition,
    typed_conclusion,
)

QUESTION = "Did the authors compare cross-lingual and single-language evaluation?"


def _audit(relationship: str) -> tuple[TypedConclusion, dict[str, Any]]:
    proposition = build_question_proposition(QUESTION)
    conclusion = typed_conclusion(proposition, "yes")
    audit = conclusion_audit_attestation(
        conclusion,
        {
            "conclusion_entailed": True,
            "polarity_consistent": True,
            "quantifier_consistent": True,
            "scope_consistent": True,
        },
        auditor_relationship=relationship,
        model="independent-test-auditor",
        seed=8,
    )
    return conclusion, audit


def test_typed_question_proposition_and_conclusion_audit_bind_by_digest() -> None:
    proposition = build_question_proposition(QUESTION)
    conclusion, audit = _audit("distinct_model")

    assert isinstance(proposition, QuestionProposition)
    assert proposition.as_dict()["proposition_id"] == proposition.proposition_id
    assert conclusion.proposition_id == proposition.proposition_id
    typed_audit = ConclusionAudit(
        conclusion_id=audit["conclusion_id"],
        conclusion_entailed=audit["conclusion_entailed"],
        polarity_consistent=audit["polarity_consistent"],
        quantifier_consistent=audit["quantifier_consistent"],
        scope_consistent=audit["scope_consistent"],
        auditor_relationship=audit["auditor_relationship"],
        model=audit["model"],
        seed=audit["seed"],
    )
    assert isinstance(typed_audit, ConclusionAudit)
    assert (
        conclusion_audit_validation_reason(audit, conclusion, release_mode=True) == ""
    )


def test_release_mode_rejects_same_instance_conclusion_auditor() -> None:
    conclusion, audit = _audit("same_instance")

    assert (
        conclusion_audit_validation_reason(audit, conclusion, release_mode=True)
        == "release_conclusion_auditor_not_independent"
    )


def test_incomplete_question_proposition_is_repaired_before_conclusion() -> None:
    question = "Does the model have attention?"

    resolution = resolve_question_proposition(question)

    assert question_proposition_completeness_reason(resolution.initial) == (
        "question_proposition_predicate_unspecified"
    )
    assert resolution.status == "repaired"
    assert resolution.repair_kind == "deterministic_main_clause"
    assert resolution.proposition.predicate == "have"
    assert resolution.proposition.subject_surface == "the model"
    assert resolution.proposition.object_surface == "attention"
    assert question_proposition_completeness_reason(resolution.proposition) == ""
    conclusion = typed_conclusion(resolution.proposition, "yes")
    assert conclusion.predicate == "have"
    assert conclusion.object_surface == "attention"


def test_qasper_characterization_questions_resolve_to_complete_main_clause() -> None:
    expected = {
        "Do they add one latent variable for each language pair in their Bayesian model?": (
            "add",
            "one latent variable for each language pair in their Bayesian model",
        ),
        "Do they inspect their model to see if their model learned to associate image parts with words related to entities?": (
            "inspect",
            "their model to see if their model learned to associate image parts with words related to entities",
        ),
        "Does this method help in sentiment classification task improvement?": (
            "help",
            "in sentiment classification task improvement",
        ),
        "Does the experiments focus on a specific domain?": (
            "focus_on",
            "a specific domain",
        ),
        "Are the automatically constructed datasets subject to quality control?": (
            "be_subject_to",
            "quality control",
        ),
        "Is car-speak language collection of abstract features that classifier is later trained on?": (
            "be_collection_of",
            "abstract features that classifier is later trained on",
        ),
    }

    for question, (predicate, object_surface) in expected.items():
        resolution = resolve_question_proposition(question)
        assert resolution.status == "repaired"
        assert resolution.proposition.predicate == predicate
        assert resolution.proposition.object_surface == object_surface
        assert question_proposition_completeness_reason(resolution.proposition) == ""


def test_qasper_characterization_keeps_already_complete_collect_proposition() -> None:
    resolution = resolve_question_proposition("Did they collected the two datasets?")

    assert resolution.status == "complete"
    assert resolution.repair_kind == "none"
    assert resolution.proposition.predicate == "collect"
    assert resolution.proposition.subject_surface == "they"
    assert resolution.proposition.object_surface == "the two datasets"


def test_nested_clause_does_not_replace_the_main_question_predicate() -> None:
    resolution = resolve_question_proposition(
        "Did the authors evaluate whether the model improved accuracy?"
    )

    assert resolution.status == "complete"
    assert resolution.proposition.actor == "current_paper"
    assert resolution.proposition.predicate == "evaluate"
    assert resolution.proposition.subject_surface == "the authors"
    assert resolution.proposition.object_surface == (
        "whether the model improved accuracy"
    )
    assert resolution.proposition.quantifier == "none"


def test_experiment_with_alias_resolves_to_complete_evaluate_proposition() -> None:
    resolution = resolve_question_proposition(
        "Did the authors experiment with the toolkits?"
    )

    assert resolution.status == "repaired"
    assert resolution.proposition.actor == "current_paper"
    assert resolution.proposition.predicate == "evaluate"
    assert resolution.proposition.subject_surface == "the authors"
    assert resolution.proposition.object_surface == "the toolkits"
    assert resolution.proposition.quantifier == "none"


def test_qasper_characterization_polarity_is_checked_without_a_model() -> None:
    cases = (
        (
            "Do they add one latent variable for each language pair in their Bayesian model?",
            "yes",
            "We add one crosslingual latent variable for each language pair.",
            "aligned",
        ),
        (
            "Do they inspect their model to see if their model learned to associate image parts with words related to entities?",
            "yes",
            "The authors do not inspect the model for those associations.",
            "contradiction_detected",
        ),
        (
            "Are the automatically constructed datasets subject to quality control?",
            "no",
            "The automatically constructed datasets are not subject to quality control.",
            "aligned",
        ),
        (
            "Did they collected the two datasets?",
            "no",
            "The authors collected the two datasets.",
            "contradiction_detected",
        ),
        (
            "Is car-speak language collection of abstract features that classifier is later trained on?",
            "no",
            "Car-speak language is not a collection of abstract features.",
            "aligned",
        ),
    )

    for question, verdict, quote, expected_status in cases:
        conclusion = typed_conclusion(build_question_proposition(question), verdict)
        check = polarity_contradiction_check(conclusion, [{"quote": quote}])
        assert check["status"] == expected_status
        assert check["independent_from_models"] is True
