from __future__ import annotations

from ktem.docqa.boolean_claim_verification import boolean_evidence_assessment
from ktem.docqa.boolean_evidence_scope import (
    boolean_proposition_evidence_score,
    boolean_retrieval_query,
    resolve_closed_scope_boolean,
    validate_boolean_scope,
)


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
