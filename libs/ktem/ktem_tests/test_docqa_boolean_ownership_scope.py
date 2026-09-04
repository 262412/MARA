from __future__ import annotations

from ktem.docqa.boolean_claim_verification import boolean_claim_authority
from ktem.docqa.boolean_evidence_scope import resolve_closed_scope_boolean
from ktem.docqa.boolean_proposition_candidates import (
    boolean_proposition_candidate_score,
)
from ktem.docqa.boolean_proposition_evidence import boolean_proposition_evidence_score

QUESTION = "Do they report results only on English data?"


def _item(evidence_id: str, text: str) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "text": text,
    }


def test_related_work_non_english_scope_is_rejected_by_every_authority_consumer() -> None:
    item = _item(
        "related-non-english",
        (
            "## Related Work\n\n"
            "The research has also been active on non-English datasets. "
            "Goudas et al. focused on user-generated Greek texts and reported "
            "annotation agreement."
        ),
    )

    assert resolve_closed_scope_boolean(QUESTION, [item]) is None
    assert boolean_proposition_candidate_score(QUESTION, item) == 0.0
    assert boolean_proposition_evidence_score(QUESTION, item) == 0.0

    authority = boolean_claim_authority(QUESTION, "no", [item])

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.canonical_answer_polarity == ""
    assert authority.supporting == ()


def test_current_study_english_scope_wins_over_related_work_counterexample() -> None:
    related_work = _item(
        "related-non-english",
        (
            "## Related Work\n\n"
            "The research has also been active on non-English datasets. "
            "Goudas et al. focused on user-generated Greek texts."
        ),
    )
    current_study = _item(
        "current-english-scope",
        (
            "## Topics and registers\n\n"
            "As a main field of interest in the current study, we chose "
            "controversies in education. We identified the current topics in "
            "education in English-speaking countries and compiled the corpus "
            "used in our experiments."
        ),
    )

    authority = boolean_claim_authority(
        QUESTION,
        "no",
        [related_work, current_study],
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    assert authority.semantic_correction_applied is True
    assert authority.supporting
    assert all(value.actor == "current_paper" for value in authority.supporting)
    assert all(
        value.evidence_id == "evidence:paper:current-english-scope"
        for value in authority.supporting
    )


def test_only_quantifier_on_another_relation_does_not_create_a_conflict() -> None:
    item = {
        **_item(
            "multilingual-results",
            (
                "We report test-set results for French and German. "
                "The English development data is used only for model selection."
            ),
        ),
        "section_id": "results",
    }

    resolution = resolve_closed_scope_boolean(QUESTION, [item])
    authority = boolean_claim_authority(QUESTION, "no", [item])

    assert resolution is not None
    assert resolution.polarity == "no"
    assert resolution.evidence_quote == (
        "We report test-set results for French and German."
    )
    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "no"
    assert authority.contradicting == ()
