from __future__ import annotations

import pytest
from ktem.docqa.boolean_claim_verification import boolean_claim_authority
from ktem.docqa.boolean_proposition_candidates import (
    boolean_proposition_candidate_score,
)
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_planning import build_query_plan


def _item(text: str, *, section_id: str = "results") -> dict[str, object]:
    return {
        "evidence_id": "anonymous-evidence",
        "source_id": "anonymous-paper",
        "section_id": section_id,
        "text": text,
    }


@pytest.mark.parametrize(
    ("question", "evidence"),
    (
        (
            "Is the clinical corpus anonymized?",
            (
                "We release a clinical corpus for evaluation. Both the recordings "
                "and their transcripts are anonymized before use."
            ),
        ),
        (
            "Does the sequence model have an attention mechanism?",
            (
                "Our sequence decoder consumes the encoder states through an "
                "attention mechanism."
            ),
        ),
        (
            "Is the system evaluated on low-resource languages?",
            (
                "We evaluate our system on six target languages. Hindi has limited "
                "training resources and is treated as a low-resource language."
            ),
        ),
        (
            "Do the authors use measures besides automatic overlap scores?",
            (
                "We report automatic overlap scores. We also conduct human "
                "evaluations of readability and coverage."
            ),
        ),
        (
            "Does the representation model capture semantics?",
            (
                "Our vector representation captures semantic relationships between "
                "terms in the corpus."
            ),
        ),
        (
            "Does the entity recognizer learn from both text and images?",
            (
                "Our proposed entity recognizer combines word vectors with visual "
                "features extracted from each image."
            ),
        ),
        (
            "Does the paper report baseline performance on regional language "
            "identification?",
            (
                "We compare our classifier with three public language-identification "
                "baselines. Table 2 reports identification accuracy across the "
                "regional languages."
            ),
        ),
    ),
)
def test_semantically_equivalent_current_paper_proposition_is_authoritative(
    question: str,
    evidence: str,
) -> None:
    authority = boolean_claim_authority(
        question,
        "unanswerable",
        [_item(evidence)],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    [support] = authority.supporting
    assert support.quote in evidence
    assert support.evidence_id == "evidence:anonymous-paper:anonymous-evidence"
    assert support.evidence_ref == support.span_id
    assert support.actor == "current_paper"
    assert support.relation
    assert support.object


@pytest.mark.parametrize(
    ("question", "evidence"),
    (
        (
            "Does the current sequence model have an attention mechanism?",
            "Prior work used a sequence model with attention for this task.",
        ),
        (
            "Did the authors evaluate their model on clinical records?",
            (
                "Our model is introduced in this section. Another study evaluated "
                "a different model on clinical records."
            ),
        ),
        (
            "Did the authors evaluate an additional corpus?",
            "The paper describes one corpus but does not state another evaluation.",
        ),
    ),
)
def test_semantic_authority_remains_fail_closed_across_scope_or_missing_assertion(
    question: str,
    evidence: str,
) -> None:
    authority = boolean_claim_authority(question, "yes", [_item(evidence)])

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.canonical_answer_polarity == ""
    assert authority.supporting == ()


def test_direct_application_to_an_alternative_corpus_defeats_primary_only_scope() -> (
    None
):
    question = "Do the authors evaluate their method on any corpus other than Alpha?"
    items = [
        _item("We evaluate the method on the Alpha corpus using abstracts only."),
        {
            **_item("We also applied our method to the Beta corpus."),
            "evidence_id": "alternative-evidence",
        },
    ]

    authority = boolean_claim_authority(
        question,
        "no",
        items,
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    [support] = authority.supporting
    assert support.evidence_id == "evidence:anonymous-paper:alternative-evidence"
    assert "Beta corpus" in support.quote


def test_negation_on_comparability_does_not_negate_a_prior_evaluation() -> None:
    question = "Were any of these tasks evaluated in prior research?"
    items = [
        _item(
            "Earlier researchers evaluated the parsing and tagging tasks.",
            section_id="related_work",
        ),
        {
            **_item(
                "Our scores are not directly comparable to values reported in "
                "prior research.",
                section_id="results",
            ),
            "evidence_id": "comparison-evidence",
        },
    ]

    authority = boolean_claim_authority(
        question,
        "unanswerable",
        items,
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    assert authority.contradicting == ()
    assert any("evaluated" in support.quote for support in authority.supporting)


def test_failure_without_target_supports_target_effectiveness() -> None:
    authority = boolean_claim_authority(
        "Is pre-training effective in this evaluation?",
        "unanswerable",
        [
            _item(
                "The model without pre-training fails to converge and produces "
                "lower evaluation accuracy."
            )
        ],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    assert authority.contradicting == ()


def test_unrelated_superlative_negation_does_not_negate_an_attribute() -> None:
    authority = boolean_claim_authority(
        "Is the template model realistic?",
        "unanswerable",
        [
            _item(
                "The template model produces coherent, readable outputs. It is "
                "never the best system by accuracy, but remains competitive."
            )
        ],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    assert authority.contradicting == ()


def test_opposite_results_in_distinct_model_conditions_remain_a_conflict() -> None:
    authority = boolean_claim_authority(
        "Does auxiliary syntax help sentiment classification?",
        "unanswerable",
        [
            _item(
                "On sentiment classification, auxiliary syntax helps the base "
                "model without contextual representations. On sentiment "
                "classification, it offers little benefit to the contextual model."
            )
        ],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "conflicting"
    assert authority.canonical_answer_polarity == ""
    assert authority.supporting
    assert authority.contradicting


def test_deictic_method_identity_cannot_bind_to_an_unnamed_feature_family() -> None:
    authority = boolean_claim_authority(
        "Does this method help sentiment classification?",
        "yes",
        [
            _item(
                "On sentiment classification, shallow feature groups offer little "
                "benefit to contextual encoders."
            )
        ],
    )

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.canonical_answer_polarity == ""


def test_deictic_method_identity_binds_to_an_explicit_current_method() -> None:
    authority = boolean_claim_authority(
        "Does this method help sentiment classification?",
        "unanswerable",
        [_item("Our proposed method improves sentiment classification accuracy.")],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"


@pytest.mark.parametrize(
    "evidence",
    (
        "We will evaluate the model on clinical tasks.",
        "We plan to evaluate the model on clinical tasks.",
        "We intend to evaluate the model on clinical tasks.",
    ),
)
def test_prospective_proposition_never_becomes_current_authority(
    evidence: str,
) -> None:
    authority = boolean_claim_authority(
        "Did the authors evaluate the model on clinical tasks?",
        "unanswerable",
        [_item(evidence)],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.canonical_answer_polarity == ""
    assert authority.supporting == ()
    assert authority.reason == "no_exact_boolean_authority"
    assert (
        boolean_proposition_candidate_score(
            "Did the authors evaluate the model on clinical tasks?",
            _item(evidence),
        )
        == 0.0
    )


def test_modal_language_outside_target_clause_does_not_block_authority() -> None:
    evidence = (
        "We evaluated the model on the current clinical tasks, while future "
        "work could extend the clinical task suite."
    )

    authority = boolean_claim_authority(
        "Did the authors evaluate the model on clinical tasks?",
        "unanswerable",
        [_item(evidence)],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    [support] = authority.supporting
    assert "we evaluated the model" in support.quote.lower()
    assert (
        boolean_proposition_candidate_score(
            "Did the authors evaluate the model on clinical tasks?",
            _item(evidence),
        )
        > 0.0
    )


def test_nominalized_evaluation_establishes_exact_boolean_authority() -> None:
    evidence = "Our evaluation of the model covers clinical tasks."
    authority = boolean_claim_authority(
        "Did the authors evaluate the model on clinical tasks?",
        "unanswerable",
        [_item(evidence)],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    [support] = authority.supporting
    assert support.relation == "evaluate"
    assert support.object == "clinical model task"
    assert support.quote == evidence


def test_deictic_dataset_cannot_bind_to_multiple_distinct_objects() -> None:
    items = [
        {**_item("We evaluated the Alpha dataset."), "evidence_id": "alpha"},
        {**_item("We evaluated the Beta dataset."), "evidence_id": "beta"},
    ]

    authority = boolean_claim_authority(
        "Did the authors evaluate this dataset?",
        "unanswerable",
        items,
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "conflicting"
    assert authority.canonical_answer_polarity == ""
    assert authority.supporting == ()
    assert authority.reason == "ambiguous_deictic_object_binding"


@pytest.mark.parametrize(
    ("question", "evidence"),
    (
        (
            "Are the answers double annotated?",
            "Each answer was annotated independently by two annotators.",
        ),
    ),
)
def test_annotation_count_synonyms_bind_to_a_typed_count_atom(
    question: str,
    evidence: str,
) -> None:
    item = _item(evidence, section_id="results")

    authority = boolean_claim_authority(
        question,
        "unanswerable",
        [item],
        allow_missing_polarity=True,
    )

    assert boolean_proposition_candidate_score(question, item) > 0.0
    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    [support] = authority.supporting
    assert support.evidence_id == identity_of(item).key
    assert support.quote == evidence
    assert support.evidence_ref == support.span_id
    assert support.actor == "current_paper"
    assert support.relation == "annotate"
    assert support.object == "annotation count"
    assert support.quantifier == "count:2"
    assert support.polarity == "yes"


@pytest.mark.parametrize(
    "evidence",
    (
        "Every question in the test set is answered by at least two additional experts.",
        "Each answer was labeled independently by two additional experts.",
    ),
)
def test_annotation_count_lower_bound_is_candidate_but_not_exact_authority(
    evidence: str,
) -> None:
    question = "Are the answers double (and not triple) annotated?"
    item = _item(evidence, section_id="results")
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )

    [slot] = bind_evidence_slots(plan, [item]).evidence_slots
    authority = boolean_claim_authority(
        question,
        "unanswerable",
        [item],
        allow_missing_polarity=True,
    )

    assert boolean_proposition_candidate_score(question, item) > 0.0
    assert slot.status == "retrieved_unverified"
    assert slot.evidence_ids == (identity_of(item).key,)
    assert authority is not None
    assert authority.status == "unknown"
    assert authority.canonical_answer_polarity == ""
    assert authority.supporting == ()


def test_annotation_count_binding_keeps_retrieval_unverified_until_exact_authority() -> None:
    question = "Are the answers double annotated?"
    item = _item(
        "Each answer was labeled independently by two annotators.",
        section_id="results",
    )
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )

    [slot] = bind_evidence_slots(plan, [item]).evidence_slots

    assert slot.slot_id == "support:boolean_proposition"
    assert slot.status == "retrieved_unverified"
    assert slot.evidence_ids == (identity_of(item).key,)


def test_annotation_count_without_target_specific_negative_stays_unknown() -> None:
    question = "Are the answers double (and not triple) annotated?"
    evidence = _item("Each answer was annotated independently.", section_id="methods")

    authority = boolean_claim_authority(question, "no", [evidence])

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.canonical_answer_polarity == ""
    assert authority.supporting == ()


@pytest.mark.parametrize(
    "evidence",
    (
        "The answers were annotated, but the number of annotators is not stated.",
        "The answers were not triple annotated.",
    ),
)
def test_annotation_count_no_requires_explicit_target_negative(evidence: str) -> None:
    question = "Are the answers double (and not triple) annotated?"

    authority = boolean_claim_authority(question, "no", [_item(evidence)])

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.canonical_answer_polarity == ""
