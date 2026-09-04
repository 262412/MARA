from __future__ import annotations

import pytest
from ktem.docqa.boolean_claim_verification import boolean_claim_authority


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
            "Do the authors model semantics?",
            "The geometry of our vector representation captures semantic relations.",
        ),
        (
            "Do the authors hypothesize that reader robustness is due to "
            "background knowledge?",
            (
                "The reason for this robustness, we believe, is that readers can "
                "also use background knowledge."
            ),
        ),
        (
            "Does the toolkit involve datasets for sixty classification tasks?",
            (
                "Our toolkit contains a task bank of over sixty classification "
                "tasks, including the standard benchmark suites."
            ),
        ),
        (
            "Does the decoder have attention?",
            "Our recurrent decoder with an attention mechanism generates the output.",
        ),
        (
            "Do they employ an indexing method to create a sample of a QA dataset?",
            (
                "We present an indexing method for the creation of a silver-standard "
                "QA dataset."
            ),
        ),
        (
            "Did the authors pefrorm a cross-lingual evaluation?",
            "We evaluate the system in a cross-lingual setting.",
        ),
    ),
)
def test_structured_semantic_equivalences_close_the_same_typed_frame(
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
    assert authority.supporting


@pytest.mark.parametrize(
    ("question", "evidence"),
    (
        (
            "Does the toolkit involve datasets for sixty classification tasks?",
            "The toolkit can execute sixty abstract task definitions.",
        ),
        (
            "Does the decoder have attention?",
            "The report was written with attention to decoder limitations.",
        ),
        (
            "Do the authors hypothesize that reader robustness is due to "
            "background knowledge?",
            "A cited study believes that readers use background knowledge.",
        ),
    ),
)
def test_semantic_equivalence_requires_the_typed_object_and_actor(
    question: str,
    evidence: str,
) -> None:
    authority = boolean_claim_authority(question, "yes", [_item(evidence)])

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.canonical_answer_polarity == ""


@pytest.mark.parametrize(
    ("question", "evidence", "expected"),
    (
        (
            "Is Arabic one of the four languages in the speech corpus?",
            (
                "Our speech corpus covers the following four languages: French, "
                "German, Turkish, and Chinese."
            ),
            "no",
        ),
        (
            "Is the sentiment dataset balanced?",
            (
                "The ground-truth labels contain 120 positive sentiments, 260 "
                "neutral sentiments, and 180 negative sentiments."
            ),
            "no",
        ),
        (
            "Do all decoder LSTMs have the same weights?",
            (
                "Our system uses multiple independent decoder LSTMs, one for each "
                "position, and each decoder learns a position-specific language model."
            ),
            "no",
        ),
        (
            "Did the authors collect their own data?",
            (
                "We collected bilingual data from talks extracted from an existing "
                "public corpus."
            ),
            "no",
        ),
    ),
)
def test_explicit_structured_closure_authorizes_auditable_negative_answers(
    question: str,
    evidence: str,
    expected: str,
) -> None:
    authority = boolean_claim_authority(
        question,
        "unanswerable",
        [_item(evidence)],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == expected
    [support] = authority.supporting
    assert support.quote in evidence
    assert support.evidence_ref == support.span_id


@pytest.mark.parametrize(
    ("question", "evidence"),
    (
        (
            "Is Arabic one of the four languages in the speech corpus?",
            "The speech corpus includes French and German among its languages.",
        ),
        (
            "Is the sentiment dataset balanced?",
            "The model obtains 72 accuracy and 68 recall on sentiment data.",
        ),
        (
            "Do all decoder LSTMs have the same weights?",
            (
                "Independent input streams enter the decoders, but all decoder "
                "weights are explicitly shared."
            ),
        ),
        (
            "Did the authors collect their own data?",
            "We collected our own data directly from volunteer participants.",
        ),
    ),
)
def test_structured_negative_resolution_rejects_incomplete_or_opposite_scope(
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
    assert not (
        authority.status == "supported" and authority.canonical_answer_polarity == "no"
    )


@pytest.mark.parametrize(
    ("question", "evidence"),
    (
        (
            "Is Arabic one of the five languages in AcmeSpeech?",
            (
                "AcmeSpeech currently covers five languages: French, "
                "German, Turkish, Chinese, and Swedish."
            ),
        ),
        (
            "Did the authors collect their own data?",
            (
                "We collected bilingual data from conference talks extracted "
                "from the Atlas corpus."
            ),
        ),
    ),
)
def test_structured_resolution_binds_explicit_current_scope_without_pronoun_copy(
    question: str,
    evidence: str,
) -> None:
    authority = boolean_claim_authority(
        question,
        "unanswerable",
        [_item(evidence, section_id="")],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "no"
    [support] = authority.supporting
    assert support.actor == "current_paper"
    assert support.quote in evidence


@pytest.mark.parametrize(
    ("question", "evidence", "expected"),
    (
        (
            "Do they report results only on English datasets?",
            (
                "For all tasks in our experimental study, we use English social "
                "media posts collected during the same period."
            ),
            "yes",
        ),
        (
            "Do the two evaluation datasets contain only English data?",
            (
                "We use two datasets for evaluation: the first consists of English "
                "messages, and the second includes English messages from the same "
                "source."
            ),
            "yes",
        ),
        (
            "Do the authors mention any downside of normalizing the input?",
            (
                "Some morphological information is lost during normalization, "
                "which leads to lower accuracy. Normalization therefore has both "
                "advantages and disadvantages."
            ),
            "yes",
        ),
        (
            "Are the images from a specific domain?",
            (
                "Evaluation is performed only on synthetic data. We construct the "
                "images from controlled scenes of abstract colored shapes."
            ),
            "yes",
        ),
        (
            "Does Atlas reach the best performance among all compared systems?",
            (
                "Atlas remains 0.4 F1 points behind the winning system and would "
                "rank second among all compared systems."
            ),
            "no",
        ),
        (
            "Does the paper establish that noisy-text challenges exist in this dataset?",
            (
                "We focus on messages from Chirper because of their noisy text. "
                "Our training dataset contains abundant misspellings, slang, and "
                "unusual character sequences."
            ),
            "yes",
        ),
        (
            "Was the approach used in this work fully supervised?",
            (
                "Each training chunk is labeled with its account class. We feed "
                "every labeled chunk into the recurrent classifier to predict the "
                "account class."
            ),
            "yes",
        ),
        (
            "Is this paper introducing an unsupervised spam-detection approach?",
            (
                "We train supervised classifiers on the labeled spammer and "
                "legitimate-user examples and evaluate them by cross-validation."
            ),
            "no",
        ),
        (
            "Is the lexicon the same for all languages?",
            (
                "The language identifier uses one lexicon built over all the data, "
                "including the vocabulary for every language group."
            ),
            "yes",
        ),
        (
            "Do they use an off-the-shelf NLP system to build the assistant?",
            (
                "We implemented the assistant's NLU unit with handcrafted rules "
                "and regular expressions."
            ),
            "no",
        ),
        (
            "Do the authors show examples where conflict works better than attention?",
            (
                "We show qualitative results and provide two examples where the "
                "combined conflict-and-attention model succeeds but attention alone "
                "fails."
            ),
            "yes",
        ),
        (
            "Do they analyze specific derogatory words?",
            (
                "A primary focus of this study is comparing the labels nova and "
                "vetus. Respondents describe vetus as outdated and derogatory."
            ),
            "yes",
        ),
    ),
)
def test_explicit_structured_facts_close_high_value_boolean_attributes(
    question: str,
    evidence: str,
    expected: str,
) -> None:
    authority = boolean_claim_authority(
        question,
        "unanswerable",
        [_item(evidence)],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == expected
    [support] = authority.supporting
    assert support.quote in evidence
    assert support.evidence_ref == support.span_id


@pytest.mark.parametrize(
    ("question", "evidence", "forbidden"),
    (
        (
            "Do they report results only on English datasets?",
            "We use one English dataset, while the second evaluation set is French.",
            "yes",
        ),
        (
            "Do the authors mention a downside of normalizing the input?",
            "Prior work notes a downside of parsing; our normalization improves accuracy.",
            "yes",
        ),
        (
            "Are the images from a specific domain?",
            "Prior work uses synthetic images, while we evaluate diverse web images.",
            "yes",
        ),
        (
            "Was the approach used in this work fully supervised?",
            (
                "Some chunks have labels, but our semi-supervised method also "
                "trains on unlabeled chunks."
            ),
            "yes",
        ),
        (
            "Does the paper establish that noisy-text challenges exist in this dataset?",
            (
                "Prior studies discuss spelling noise. Our dataset description "
                "does not characterize that phenomenon."
            ),
            "yes",
        ),
        (
            "Is this paper introducing an unsupervised spam-detection approach?",
            "We use LDA to extract topic features before describing the classifier.",
            "no",
        ),
        (
            "Is the lexicon the same for all languages?",
            "We build a separate lexicon for each language from its own training data.",
            "yes",
        ),
        (
            "Do they use an off-the-shelf NLP system to build the assistant?",
            (
                "We use an off-the-shelf NLP toolkit and add handcrafted rules "
                "for one optional dialogue feature."
            ),
            "no",
        ),
        (
            "Do the authors show examples where conflict works better than attention?",
            (
                "We compare aggregate attention and conflict scores, but do not "
                "provide qualitative examples."
            ),
            "yes",
        ),
        (
            "Do they analyze specific derogatory words?",
            (
                "Prior work calls one label derogatory; our study does not analyze "
                "individual labels."
            ),
            "yes",
        ),
    ),
)
def test_structured_attributes_reject_incomplete_or_opposite_scope(
    question: str,
    evidence: str,
    forbidden: str,
) -> None:
    authority = boolean_claim_authority(
        question,
        "unanswerable",
        [_item(evidence)],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert not (
        authority.status == "supported"
        and authority.canonical_answer_polarity == forbidden
    )
