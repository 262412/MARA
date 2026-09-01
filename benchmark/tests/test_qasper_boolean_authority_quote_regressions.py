from __future__ import annotations

import pytest
from ktem.docqa.boolean_claim_verification import boolean_claim_authority


def _item(evidence_id: str, text: str) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "results",
        "text": text,
    }


@pytest.mark.parametrize(
    ("question", "quote"),
    (
        (
            "Are the answers double (and not triple) annotated?",
            "Sources of disagreement among annotators include different "
            "interpretations (2%) and other reasons.",
        ),
        (
            "Do they experiment with the toolkits?",
            "We present GluonCV and GluonNLP, the deep learning toolkits. "
            "These toolkits provide reusable components.",
        ),
        (
            "Do they experiment with the toolkits?",
            "We evaluate a separate baseline on image classification. "
            "We present GluonCV and GluonNLP, the deep learning toolkits.",
        ),
        (
            "Do they test framework performance on language pairs such as "
            "English-German?",
            "We consider an under-resourced English-German pair and perform "
            "language-specific coding.",
        ),
        (
            "Do they test framework performance on commonly used language pairs?",
            "In testing time, target-language information limits translated "
            "candidates and forms the translation in the desired language pair.",
        ),
        (
            "Do they use other evaluation metrics besides ROUGE?",
            "We report results using automatic metrics in Table TABREF20.",
        ),
        (
            "Is the system evaluated on low-resource languages?",
            "We evaluate our system on six target languages. Low-resource "
            "languages are reserved for future work.",
        ),
    ),
)
def test_qasper_exact_quote_does_not_infer_a_semantic_relation(
    question: str,
    quote: str,
) -> None:
    authority = boolean_claim_authority(
        question,
        "yes",
        [_item("generic-negative", quote)],
    )

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.supporting == ()


def test_annotation_count_uses_a_non_percentage_marker_near_annotation() -> None:
    quote = "Each answer was annotated by exactly two annotators."

    authority = boolean_claim_authority(
        "Are the answers double annotated?",
        "yes",
        [_item("count-marker", quote)],
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.supporting[0].quote == quote


def test_annotation_percentage_does_not_promote_a_lower_bound_count() -> None:
    quote = (
        "The pilot set included a 2% disagreement rate. Every question was "
        "answered by at least two experts."
    )

    authority = boolean_claim_authority(
        "Are the answers double annotated?",
        "yes",
        [_item("count-lower-bound", quote)],
    )

    assert authority is not None
    assert authority.status == "unknown"


def test_not_able_to_capture_is_not_global_negative_semantic_authority() -> None:
    quote = (
        "The word2vec features were not able to capture subtle semantic "
        "distinctions."
    )

    authority = boolean_claim_authority(
        "Do they model semantics?",
        "yes",
        [_item("semantic-limitation", quote)],
    )

    assert authority is not None
    assert authority.status == "unknown"


def test_not_able_to_capture_answers_an_explicit_capability_question() -> None:
    quote = (
        "The word2vec features were not able to capture subtle semantic "
        "distinctions."
    )

    authority = boolean_claim_authority(
        "Are the word2vec features able to capture subtle semantic distinctions?",
        "no",
        [_item("semantic-capability", quote)],
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "no"


def test_other_metrics_requires_an_explicit_metric_besides_rouge() -> None:
    quote = "We report ROUGE and BLEU metrics for the evaluation."

    authority = boolean_claim_authority(
        "Do they use other evaluation metrics besides ROUGE?",
        "yes",
        [_item("explicit-metric", quote)],
    )

    assert authority is not None
    assert authority.status == "supported"


def test_empirical_action_accepts_a_locally_entity_bridged_scope() -> None:
    quote = (
        "We evaluate our approach for French, Arabic, Hindi, and Vietnamese. "
        "Hindi has far less data and can be considered a low-resource language."
    )

    authority = boolean_claim_authority(
        "Is the system tested on low-resource languages?",
        "yes",
        [_item("low-resource-evaluation", quote)],
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"


def test_test_time_description_does_not_shadow_a_direct_empirical_result() -> None:
    quote = (
        "In testing time, target-language information limits translated "
        "candidates. We evaluate translation quality on English-German and "
        "French-English benchmark language pairs."
    )

    authority = boolean_claim_authority(
        "Do they test framework performance on commonly used language pairs?",
        "yes",
        [_item("language-pair-evaluation", quote)],
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
