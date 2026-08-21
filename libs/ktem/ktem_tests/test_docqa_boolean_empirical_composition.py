from __future__ import annotations

import pytest
from ktem.docqa.boolean_claim_verification import boolean_claim_authority
from ktem.docqa.evidence_identity import identity_of


def _item(
    evidence_id: str,
    text: str,
    *,
    source_id: str = "paper",
    section_id: str = "results",
) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "section_id": section_id,
        "text": text,
    }


def test_same_source_named_entity_type_completes_an_empirical_proposition() -> None:
    definition = _item(
        "definition",
        "We present AtlasCV and AtlasNLP, two open-source toolkits for research.",
        section_id="introduction",
    )
    experiment = _item(
        "experiment",
        "In our experiments, we evaluate AtlasCV on two benchmark datasets.",
        section_id="experiments",
    )

    authority = boolean_claim_authority(
        "Did the authors experiment with the toolkits?",
        "unanswerable",
        [definition, experiment],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    [support] = authority.supporting
    assert support.evidence_id == identity_of(experiment).key
    assert support.quote == experiment["text"]
    assert support.object == "toolkit"
    assert support.reason == "same_source_entity_type_empirical_proposition"


@pytest.mark.parametrize(
    ("definition_source", "experiment_text"),
    (
        (
            "other-paper",
            "In our experiments, we evaluate AtlasCV on two benchmark datasets.",
        ),
        (
            "paper",
            "In future work, we will evaluate AtlasCV on two benchmark datasets.",
        ),
        (
            "paper",
            "In our experiments, we evaluate AtlasSpeech on two benchmark datasets.",
        ),
    ),
)
def test_entity_type_composition_rejects_cross_source_future_or_different_entities(
    definition_source: str,
    experiment_text: str,
) -> None:
    definition = _item(
        "definition",
        "We present AtlasCV and AtlasNLP, two open-source toolkits for research.",
        source_id=definition_source,
        section_id="introduction",
    )
    experiment = _item(
        "experiment",
        experiment_text,
        section_id="experiments",
    )

    authority = boolean_claim_authority(
        "Did the authors experiment with the toolkits?",
        "yes",
        [definition, experiment],
    )

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.supporting == ()


def test_human_evaluations_are_typed_as_metrics_besides_rouge() -> None:
    evidence = _item(
        "human-evaluation",
        "Experimental results are evaluated automatically in terms of ROUGE. "
        "We also conduct two human evaluations in order to assess preference "
        "and information preservation.",
    )

    authority = boolean_claim_authority(
        "Do the authors use other evaluation metrics besides ROUGE?",
        "unanswerable",
        [evidence],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    [support] = authority.supporting
    assert "ROUGE" in support.quote
    assert "human evaluations" in support.quote
    assert evidence["text"][support.span_start : support.span_end] == support.quote


def test_additional_evaluation_without_an_explicit_metric_stays_unknown() -> None:
    evidence = _item(
        "non-metric-evaluation",
        "We evaluate summaries automatically with ROUGE. We also evaluate the "
        "decoder on a held-out split.",
    )

    authority = boolean_claim_authority(
        "Do the authors use other evaluation metrics besides ROUGE?",
        "yes",
        [evidence],
    )

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.supporting == ()


def test_explicit_qualified_category_can_bind_across_one_bounded_paragraph() -> None:
    evidence = _item(
        "qualified-language",
        "We evaluate our approach for six target languages: French, Russian, "
        "Arabic, Chinese, Hindi, and Vietnamese. These languages belong to four "
        "families. French and Russian are related to English. Arabic and Chinese "
        "come from different families. The choice reflects different training "
        "conditions. Hindi has far less data and is considered a low-resource "
        "language.",
        section_id="experiments",
    )

    authority = boolean_claim_authority(
        "Is the system tested on low-resource languages?",
        "unanswerable",
        [evidence],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    [support] = authority.supporting
    assert support.quote == evidence["text"]


def test_exact_empirical_candidate_survives_pre_authority_deduplication() -> None:
    evidence = _item(
        "qualified-language-with-distractor",
        "We evaluate our approach for six target languages: French (fr), Russian "
        "(ru), Arabic (ar), Chinese (zh), Hindi (hi), and Vietnamese (vi). "
        "These languages belong to four different language families. French, "
        "Russian, and Hindi are Indo-European languages, similar to English. "
        "Arabic, Chinese, and Vietnamese come from different families. The "
        "choice reflects different training conditions. Hindi has far less data "
        "and can be considered a low-resource language.\n\nFor experiments "
        "that use parallel data to initialize foreign-specific parameters, we "
        "use the same datasets as prior work.",
        section_id="experiments",
    )

    authority = boolean_claim_authority(
        "Is the system tested on low-resource languages?",
        "unanswerable",
        [evidence],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    [support] = authority.supporting
    assert support.quote.startswith("We evaluate our approach")
    assert support.quote.endswith("a low-resource language.")


def test_qualified_category_does_not_cross_a_section_boundary() -> None:
    evidence = _item(
        "cross-section-language",
        "We evaluate our approach for six target languages. The datasets vary in "
        "size. We use the same optimizer. Results are reported separately. The "
        "evaluation ends here.\n\n## Related Work\n\nHindi is considered a "
        "low-resource language.",
        section_id="experiments",
    )

    authority = boolean_claim_authority(
        "Is the system tested on low-resource languages?",
        "yes",
        [evidence],
    )

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.supporting == ()


def test_named_language_pair_notation_supplies_the_pair_type() -> None:
    evidence = _item(
        "language-pair-result",
        "Table 4 summarizes system performance measured in BLEU on two test "
        "sets. Compared with the baseline trained on TED English-German data, "
        "our system improves by 2.6 BLEU points.",
    )

    authority = boolean_claim_authority(
        "Do they test framework performance on commonly used language pairs, "
        "such as English-to-German?",
        "unanswerable",
        [evidence],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    [support] = authority.supporting
    assert support.object == "english german language pair"
    assert "2.6 BLEU points" in support.quote
    assert evidence["text"][support.span_start : support.span_end] == support.quote


def test_testing_time_language_pair_description_is_not_an_empirical_action() -> None:
    evidence = _item(
        "test-time-description",
        "In testing time, target-language information limits English-German "
        "candidates and forms the translation in the desired language pair.",
    )

    authority = boolean_claim_authority(
        "Do they test framework performance on commonly used language pairs, "
        "such as English-to-German?",
        "yes",
        [evidence],
    )

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.supporting == ()
