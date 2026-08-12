from __future__ import annotations

import pytest
from ktem.docqa import boolean_evidence_scope as scope_evidence
from ktem.docqa.boolean_claim_verification import boolean_evidence_assessment
from ktem.docqa.boolean_evidence_scope import (
    BooleanScopeDecision,
    ClosedScopeResolution,
    boolean_proposition_evidence_score,
    boolean_retrieval_query,
    resolve_closed_scope_boolean,
    validate_boolean_scope,
)
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_planning import build_query_plan


def test_current_paper_question_rejects_unknown_actor_and_scope() -> None:
    decision = validate_boolean_scope(
        "Did the authors evaluate the model on relevant tasks?",
        "The model was evaluated on relevant tasks.",
        "yes",
        evidence_items=[
            {
                "section_title": "Introduction",
                "text": "The model was evaluated on relevant tasks.",
            }
        ],
    )

    assert decision.scope_valid is False
    assert decision.reason == "current_paper_scope_not_established"


def test_boolean_claim_verifier_ignores_related_work_polarity() -> None:
    assessment = boolean_evidence_assessment(
        "Did the authors evaluate the model on relevant tasks?",
        "no",
        [
            {
                "source_id": "paper",
                "span_id": "related-work",
                "section_title": "Related Work",
                "text": "Previous work evaluated comparable models on relevant tasks.",
            }
        ],
    )

    assert assessment is not None
    _claim, status, supporting, contradicting = assessment
    assert status == "unknown"
    assert supporting == ()
    assert contradicting == ()


def test_current_paper_experiment_question_uses_direct_empirical_evidence() -> None:
    resolution = resolve_closed_scope_boolean(
        "Do the authors conduct experiments on the tasks mentioned?",
        [
            {
                "source_id": "paper",
                "span_id": "experiment",
                "text": (
                    "For instance, the sentence is translated by Google Translate, "
                    "Bing Translate, and Yandex. In fact, I have been unable to "
                    "construct any English sentence that those systems translate "
                    "using the feminine plural pronoun."
                ),
            }
        ],
    )

    assert resolution is not None
    assert resolution.polarity == "yes"
    assert "I have been unable to construct" in resolution.evidence_quote
    assert resolution.decision.actor == "current_paper"
    assert resolution.decision.section_role == "experiments"


def test_current_experiment_resolution_preserves_explicit_exclusion_polarity() -> None:
    question = (
        "Do they experiment with their proposed model on any other dataset "
        "other than MovieQA?"
    )
    item = {
        "evidence_id": "exclusive-dataset",
        "source_id": "paper",
        "section_id": "results",
        "text": (
            "We evaluated the proposed model only on the MovieQA dataset and no "
            "other dataset."
        ),
    }

    resolution = resolve_closed_scope_boolean(question, [item])

    assert resolution is not None
    assert resolution.polarity == "no"
    assert resolution.evidence_quote == item["text"]
    assert boolean_proposition_evidence_score(question, item) > 0


def test_current_experiment_slot_score_and_binding_reuse_single_candidate_resolver() -> None:
    question = "Do the authors conduct experiments on the tasks mentioned?"
    item = {
        "evidence_id": "experiment",
        "source_id": "paper",
        "text": (
            "Sentence pairs are useful challenges for machine translation, but "
            "their construction is difficult to automate.\n\n"
            "## Current state of the art\n"
            "Machine translation systems provide broad coverage, although their "
            "handling of grammatical gender remains uneven across languages.\n\n"
            "For instance, the sentence is translated by Google Translate, Bing "
            "Translate, and Yandex. In fact, I have been unable to construct any "
            "English sentence that those systems translate using the feminine "
            "plural pronoun.\n\n"
            "The following discussion compares these observations with prior work."
        ),
    }
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )

    [slot] = plan.evidence_slots
    assert slot.statement_kind == "boolean_proposition"
    assert boolean_proposition_evidence_score(slot.metric, item) > 0

    bound = bind_evidence_slots(plan, [item])

    [bound_slot] = bound.evidence_slots
    assert bound_slot.evidence_ids == (identity_of(item).key,)
    assert bound_slot.status == "retrieved_unverified"


@pytest.mark.parametrize(
    "item",
    (
        {
            "evidence_id": "related-work",
            "source_id": "paper",
            "section_id": "related_work",
            "text": "Previous work conducted experiments on the tasks mentioned.",
        },
        {
            "evidence_id": "other-paper",
            "source_id": "paper",
            "section_id": "results",
            "text": "Smith et al. conducted experiments on the tasks mentioned.",
        },
        {
            "evidence_id": "future",
            "source_id": "paper",
            "section_id": "future_work",
            "text": "In future work, we will conduct experiments on the tasks mentioned.",
        },
        {
            "evidence_id": "hypothetical",
            "source_id": "paper",
            "section_id": "results",
            "text": "We might conduct experiments on the tasks mentioned in future work.",
        },
        {
            "evidence_id": "future-marker",
            "source_id": "paper",
            "section_id": "results",
            "text": "Our future experiments will test the tasks mentioned.",
        },
        {
            "evidence_id": "topical-only",
            "source_id": "paper",
            "section_id": "results",
            "text": "The tasks mentioned are standard benchmarks for this field.",
        },
        {
            "evidence_id": "translation-description",
            "source_id": "paper",
            "text": "We describe how systems translate the tasks mentioned.",
        },
        {
            "evidence_id": "negated-experiment",
            "source_id": "paper",
            "text": "We did not conduct experiments on the tasks mentioned.",
        },
        {
            "evidence_id": "intended-experiment",
            "source_id": "paper",
            "text": "We intend to conduct experiments on the tasks mentioned.",
        },
    ),
)
def test_current_experiment_slot_rejects_non_authoritative_scopes(item) -> None:
    assert (
        boolean_proposition_evidence_score(
            "Do the authors conduct experiments on the tasks mentioned?",
            item,
        )
        == 0.0
    )


@pytest.mark.parametrize("mismatch", ("identity", "quote"))
def test_current_experiment_slot_rejects_unbound_quote_and_identity(
    monkeypatch,
    mismatch: str,
) -> None:
    question = "Do the authors conduct experiments on the tasks mentioned?"
    candidate = {
        "evidence_id": "candidate",
        "source_id": "paper",
        "section_id": "results",
        "text": "We conducted experiments on the tasks mentioned.",
    }
    resolved_item = {
        "evidence_id": "other" if mismatch == "identity" else "candidate",
        "source_id": "paper",
        "section_id": "results",
        "text": "We conducted experiments on the tasks mentioned.",
    }
    resolved_quote = (
        resolved_item["text"]
        if mismatch == "identity"
        else "A quote that is not a substring of the candidate."
    )
    resolution = ClosedScopeResolution(
        polarity="yes",
        evidence_quote=resolved_quote,
        decision=BooleanScopeDecision(
            actor="current_paper",
            section_role="experiments",
            quantifier="none",
            scope_valid=True,
            reason="non_quantified_proposition",
        ),
        evidence_item=resolved_item,
    )
    monkeypatch.setattr(
        scope_evidence,
        "resolve_closed_scope_boolean",
        lambda _question, _items: resolution,
    )

    assert boolean_proposition_evidence_score(question, candidate) == 0.0


def test_related_work_does_not_resolve_current_paper_experiment_question() -> None:
    resolution = resolve_closed_scope_boolean(
        "Do the authors conduct experiments on the tasks mentioned?",
        [
            {
                "source_id": "paper",
                "span_id": "related-work",
                "section_title": "Related Work",
                "text": "Previous work evaluated translation systems on those tasks.",
            }
        ],
    )

    assert resolution is None


def test_boolean_slot_rejects_topical_evidence_without_requested_action() -> None:
    score = boolean_proposition_evidence_score(
        "Did the authors inspect the associations learned by the model?",
        {
            "source_id": "paper",
            "span_id": "architecture",
            "section_title": "Methods",
            "text": (
                "We introduce a multimodal attention architecture that learns "
                "associations between image and text features."
            ),
        },
    )

    assert score == 0.0


def test_boolean_slot_accepts_evidence_with_requested_action_and_object() -> None:
    score = boolean_proposition_evidence_score(
        "Did the authors inspect the associations learned by the model?",
        {
            "source_id": "paper",
            "span_id": "error-analysis",
            "section_title": "Results",
            "text": (
                "We inspect the associations learned by the model through an "
                "error analysis of modality attention."
            ),
        },
    )

    assert score > 0.0


def test_quality_validation_evidence_is_retained_for_quality_control_slot() -> None:
    question = "Are the automatically constructed datasets subject to quality control?"
    item = {
        "source_id": "paper",
        "span_id": "quality-validation",
        "section_title": "Dataset Probes",
        "text": (
            "It is much harder to validate the quality of such data at such a "
            "scale and such varying levels of complexity."
        ),
    }

    assert boolean_proposition_evidence_score(question, item) == 3.0
    assert (
        boolean_proposition_evidence_score(
            "are automatically constructed datasets subject quality control",
            item,
        )
        == 3.0
    )


def test_annotation_artifact_control_is_not_complete_quality_validation() -> None:
    question = "Are the automatically constructed datasets subject to quality control?"
    item = {
        "source_id": "paper",
        "span_id": "artifact-control",
        "section_title": "Dataset Probes",
        "text": (
            "We find automatically constructing probes to be vulnerable to "
            "annotation artifacts, which we carefully control for."
        ),
    }

    assert boolean_proposition_evidence_score(question, item) == 1.0


def test_quality_control_query_retrieves_validation_terms() -> None:
    query = boolean_retrieval_query(
        "Are the automatically constructed datasets subject to quality control?"
    )

    assert "validate quality" in query
    assert "annotation artifacts" in query
