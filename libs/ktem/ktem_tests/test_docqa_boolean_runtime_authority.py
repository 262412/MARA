from __future__ import annotations

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_claim_verification import boolean_claim_authority
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn


def _evidence(
    evidence_id: str,
    text: str,
    *,
    section_id: str = "results",
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": section_id,
        "text": text,
    }


def _run_boolean(
    question: str,
    generated_answer: str,
    items: list[dict[str, object]],
    *,
    route_policy: str = "doc",
):
    return execute_controller_turn(
        DocQARequest(
            prompt=question,
            retrieval_query=question,
            task_type="boolean",
            verification_mode="strict",
            verification_domain="qasper",
            route_policy=route_policy,
            allowed_routes=["doc_text", "hybrid"],
            selected_file_ids=["paper"],
            origin="benchmark",
        ),
        retrieve=lambda *_args: {"evidence": items},
        generate=lambda *_args: generated_answer,
    )


@pytest.mark.parametrize("route_policy", ("doc", "auto", "hybrid"))
def test_111_runtime_commits_exact_qualifier_aware_no_authority(
    route_policy: str,
) -> None:
    question = (
        "Overall, does having parallel data improve semantic role induction "
        "across multiple languages?"
    )
    subject = (
        "Our multilingual model transfers semantic roles with word alignments "
        "from parallel data in both languages."
    )
    decisive = (
        "Comparing with Line 2, we get non-significant improvements in both "
        "languages."
    )
    item = _evidence(
        "parallel-result",
        f"The evaluation uses the same corpus split. {subject} {decisive} "
        "However, the monolingual baseline remains competitive.",
    )

    result = _run_boolean(
        question,
        (
            "Overall, no. The results show only small improvements across the "
            "two languages."
        ),
        [item],
        route_policy=route_policy,
    )

    assert result.answer == "no"
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.canonical_answer_polarity == "no"
    assert result.verify_decision.authoritative_evidence_id == identity_of(item).key
    assert decisive in result.verify_decision.authoritative_quote
    assert subject in result.verify_decision.authoritative_quote
    [claim] = result.verify_decision.claim_results
    assert claim["actor"] == "current_paper"
    assert claim["relation"] == "improve"
    assert claim["predicate"] == "improve"
    assert claim["arguments"]
    assert claim["qualifier"] == "non_significant"
    assert claim["scope"] == claim["section_scope"]
    assert claim["verified_slot_state"] == "verified_support"
    [span] = claim["supporting_evidence_spans"]
    assert span["predicate"] == "improve"
    assert span["qualifier"] == "non_significant"
    assert span["scope"] == span["section_scope"]
    metadata = result.evidence_bundle.metadata
    assert metadata["query_plan"]["stage"] == "verified"
    assert metadata["query_plan"]["state_authority"] == "verified_claim_support.v1"
    [slot] = metadata["query_plan"]["evidence_slots"]
    assert slot["status"] == "verified_support"
    assert slot["evidence_ids"] == [identity_of(item).key]


@pytest.mark.parametrize("route_policy", ("doc", "auto", "hybrid"))
def test_1dc_runtime_corrects_generated_polarity_before_terminal_commit(
    route_policy: str,
) -> None:
    question = "Do the authors conduct experiments on the tasks mentioned?"
    item = _evidence(
        "experiment",
        (
            "## Current state of the art\n"
            "For instance, the sentence is translated by Google Translate, "
            "Bing Translate, and Yandex. In fact, we have been unable to "
            "construct any English sentence that those systems translate using "
            "the feminine plural pronoun."
        ),
        section_id="experiments",
    )

    result = _run_boolean(
        question,
        "The authors do not conduct experiments on the tasks mentioned.\nAnswer: no",
        [item],
        route_policy=route_policy,
    )

    assert result.answer == "yes"
    assert result.guardrail_decision.action == "return"
    assert result.verify_decision.input_answer_polarity == "no"
    assert result.verify_decision.canonical_answer_polarity == "yes"
    assert result.verify_decision.semantic_correction_applied is True
    assert result.verify_decision.authoritative_evidence_id == identity_of(item).key
    assert result.verify_decision.authoritative_quote in str(item["text"])


@pytest.mark.parametrize("route_policy", ("doc", "auto", "hybrid"))
def test_1dc_runtime_recovers_exact_authority_from_generated_abstention(
    route_policy: str,
) -> None:
    question = "Do the authors conduct experiments on the tasks mentioned?"
    item = _evidence(
        "experiment",
        (
            "## Current state of the art\n"
            "For instance, the sentence is translated by Google Translate, "
            "Bing Translate, and Yandex. In fact, we have been unable to "
            "construct any English sentence that those systems translate using "
            "the feminine plural pronoun."
        ),
        section_id="experiments",
    )

    result = _run_boolean(
        question,
        "unanswerable The context does not mention experiments on these tasks.",
        [item],
        route_policy=route_policy,
    )

    assert result.answer == "yes"
    assert result.guardrail_decision.action == "return"
    assert result.verify_decision.input_answer_polarity == ""
    assert result.verify_decision.canonical_answer_polarity == "yes"
    assert result.verify_decision.semantic_correction_applied is True
    assert result.verify_decision.authoritative_evidence_id == identity_of(item).key


def test_348_runtime_resolves_closed_only_scope_to_no() -> None:
    question = "Do they report results only on English dataset?"
    item = _evidence(
        "multilingual-results",
        (
            "We report the 2016 and 2018 test-set results for French and German. "
            "The English development data is used only for model selection."
        ),
    )

    result = _run_boolean(
        question,
        "No. The reported results include French and German.",
        [item],
        route_policy="auto",
    )

    assert result.answer == "no"
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.canonical_answer_polarity == "no"
    assert result.verify_decision.quantifier == "only"


@pytest.mark.parametrize("route_policy", ("doc", "auto", "hybrid"))
def test_b065_runtime_resolves_exclusive_requirement_to_no(
    route_policy: str,
) -> None:
    question = (
        "Is fine-tuning required to incorporate these embeddings into existing "
        "models?"
    )
    decisive = (
        "The only requirement is that the model accepts as input, an embedding "
        "layer for entities and relations."
    )
    item = _evidence(
        "drop-in-requirement",
        (
            "It is very easy to incorporate the learned embeddings into existing "
            f"predictive models. {decisive} We can use them as a drop-in "
            "replacement and initialize the corresponding embedding layer."
        ),
        section_id="methods",
    )

    result = _run_boolean(
        question,
        "No. Fine-tuning is not required for the drop-in replacement.",
        [item],
        route_policy=route_policy,
    )

    assert result.answer == "no"
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.canonical_answer_polarity == "no"
    assert result.verify_decision.authoritative_evidence_id == identity_of(item).key
    assert decisive in result.verify_decision.authoritative_quote


@pytest.mark.parametrize("route_policy", ("doc", "auto", "hybrid"))
def test_d274_previous_work_question_accepts_exact_cited_work_scope(
    route_policy: str,
) -> None:
    question = "Were any of these tasks evaluated in any previous work?"
    item = _evidence(
        "prior-work",
        (
            "Recent work assessed the ability of LSTMs to learn subject-verb "
            "agreement patterns in English and evaluated naturally occurring "
            "sentences. Other prior work considered reflexive anaphora and "
            "negative polarity items using manually constructed stimuli."
        ),
        section_id="related_work",
    )

    result = _run_boolean(
        question,
        "Yes. Previous work evaluated these tasks.",
        [item],
        route_policy=route_policy,
    )

    assert result.answer == "yes"
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.authoritative_evidence_id == identity_of(item).key


@pytest.mark.parametrize(
    ("question", "text", "answer"),
    (
        (
            "Did the authors evaluate the model on clinical tasks?",
            "Previous work evaluated the model on clinical tasks.",
            "yes",
        ),
        (
            "Did the authors use their own training data?",
            "Other researchers used their own training data.",
            "yes",
        ),
        (
            "Did every language improve?",
            "English improved, but the other languages were not reported.",
            "yes",
        ),
        (
            "Did the authors omit data other than English?",
            "The paper describes English data without stating an exclusive scope.",
            "no",
        ),
    ),
)
def test_boolean_runtime_hard_negatives_remain_fail_closed(
    question: str,
    text: str,
    answer: str,
) -> None:
    result = _run_boolean(question, answer, [_evidence("context", text)])

    assert result.answer == ABSTAIN_MESSAGE
    assert result.verify_decision.status in {
        "unknown",
        "unsupported",
        "not_enough_evidence",
    }
    assert result.guardrail_decision.action == "abstain"
    assert "query_plan" not in result.evidence_bundle.metadata or (
        result.evidence_bundle.metadata["query_plan"].get("stage") != "verified"
    )


@pytest.mark.parametrize(
    ("question", "text"),
    (
        (
            "Did they compare with other extractive summarization methods?",
            (
                "Overall, the upper-bound analysis concerns extractive "
                "summarization alone. While CUI comparison allows for comparing "
                "medically relevant concepts, the CUI labelling process is not "
                "perfect and further work is needed."
            ),
        ),
        (
            "Is the dataset for sentiment analysis balanced?",
            (
                "Among commercial NLP toolkits, we selected two publicly "
                "accessible APIs for entity-level sentiment analysis that are "
                "agnostic to the text domain."
            ),
        ),
        (
            "Did the authors experiment with this new dataset?",
            (
                "This new dataset complements the earlier release by providing "
                "experiments designed to analyze differences between natural "
                "reading and annotation."
            ),
        ),
        (
            "Did the authors experiment with other tasks?",
            (
                "Two separate models are developed for the tasks. The NER task "
                "is solved with a BiLSTM-CRF model and the RE task uses a "
                "multi-head selection approach."
            ),
        ),
        (
            "Are humans and machine learning systems fooled by the same kinds "
            "of illusions?",
            (
                "Machine-learning systems are susceptible to adversarial "
                "examples and may be brittle and easily fooled. Human cognition "
                "is assumed to yield robust systems."
            ),
        ),
    ),
)
def test_false_positive_proposition_shapes_never_become_authority(
    question: str,
    text: str,
) -> None:
    result = _run_boolean(question, "yes", [_evidence("near-match", text)])

    assert result.answer == ABSTAIN_MESSAGE
    assert result.verify_decision.canonical_answer_polarity == ""
    assert result.guardrail_decision.action == "abstain"


def test_non_significant_qualifier_controls_overall_improvement_polarity() -> None:
    question = (
        "Overall, does having parallel data improve semantic role induction "
        "across multiple languages?"
    )
    decisive = "We get non-significant improvements in both languages."
    item = _evidence(
        "qualified-improvement",
        (
            "The multilingual model adds word alignments from parallel data. "
            f"{decisive} The multilingual model obtains small improvements in "
            "both languages. These results indicate that little information can "
            "be learned about semantic roles from this parallel data setup."
        ),
    )

    result = _run_boolean(question, "yes", [item])

    assert result.answer == "no"
    assert result.verify_decision.semantic_correction_applied is True
    assert decisive in result.verify_decision.authoritative_quote
    [span] = result.verify_decision.claim_results[0]["supporting_evidence_spans"]
    assert span["qualifier"] == "non_significant"


def test_lexical_candidate_never_becomes_boolean_authority() -> None:
    question = "Did the authors release source code?"
    item = _evidence(
        "lexical-only",
        "The source code section discusses release engineering terminology.",
    )

    result = _run_boolean(question, "Yes.", [item])

    assert result.answer == ABSTAIN_MESSAGE
    [slot] = result.evidence_bundle.metadata["bound_query_plan"]["evidence_slots"]
    assert slot["status"] in {"retrieved_unverified", "retrieved_partial", "missing"}
    assert slot["status"] != "verified_support"


def test_generated_abstention_without_exact_authority_remains_fail_closed() -> None:
    question = "Did the authors release source code?"
    item = _evidence(
        "lexical-only",
        "The source code section discusses release engineering terminology.",
    )

    result = _run_boolean(
        question,
        "unanswerable The evidence does not establish a release.",
        [item],
    )

    assert result.answer == ABSTAIN_MESSAGE
    assert result.verify_decision.input_answer_polarity == ""
    assert result.verify_decision.canonical_answer_polarity == ""
    assert result.guardrail_decision.action == "abstain"


def test_requirement_negative_qualifier_overrides_exclusive_requirement_match() -> None:
    question = "Did the authors require fine-tuning the model?"
    evidence = _evidence(
        "requirement-negative",
        (
            "The only requirement is that the model accepts embeddings; "
            "fine-tuning is not needed."
        ),
    )

    authority = boolean_claim_authority(question, "yes", [evidence])

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "no"
    assert authority.semantic_correction_applied is True
    assert authority.supporting[0].relation == "require"
    assert authority.supporting[0].quantifier == "only"


def test_requirement_without_qualifier_is_negative_authority() -> None:
    question = (
        "Is fine-tuning required to incorporate these embeddings into existing "
        "models?"
    )
    evidence = _evidence(
        "requirement-without",
        "The embeddings can be used as a drop-in replacement without fine-tuning.",
        section_id="methods",
    )

    authority = boolean_claim_authority(question, "yes", [evidence])

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "no"
    assert authority.semantic_correction_applied is True
    assert authority.supporting[0].relation == "require"
    assert authority.supporting[0].qualifier == "not_required"


def test_boolean_authority_serializes_generic_proposition_schema() -> None:
    question = (
        "Overall, does having parallel data improve semantic role induction "
        "across multiple languages?"
    )
    item = _evidence(
        "schema-authority",
        (
            "Our multilingual model uses parallel data for semantic role induction. "
            "Comparing with Line 2, we get non-significant improvements in both "
            "languages."
        ),
    )

    authority = boolean_claim_authority(question, "no", [item])

    assert authority is not None
    [support] = authority.supporting
    payload = support.as_dict()
    assert {
        "actor",
        "predicate",
        "object",
        "polarity",
        "qualifier",
        "quantifier",
        "scope",
    } <= payload.keys()
    assert payload["predicate"] == "improve"
    assert payload["qualifier"] == "non_significant"
    assert payload["scope"] == payload["section_scope"]


def test_boolean_authority_expands_to_nonadjacent_same_experiment_frame() -> None:
    question = (
        "Overall, does having parallel data improve semantic role induction "
        "across multiple languages?"
    )
    subject = (
        "Our multilingual model transfers semantic roles with word alignments "
        "from parallel data in both languages."
    )
    bridge = "All systems use the same evaluation corpus split."
    decisive = (
        "Comparing with Line 2, we get non-significant improvements in both "
        "languages."
    )
    unrelated = "Prior work reports a different monolingual benchmark."
    text = " ".join((subject, bridge, decisive, unrelated))
    item = _evidence("semantic-expansion", text)

    authority = boolean_claim_authority(question, "no", [item])

    assert authority is not None
    [support] = authority.supporting
    assert subject in support.quote
    assert bridge in support.quote
    assert decisive in support.quote
    assert unrelated not in support.quote
    assert text[support.span_start : support.span_end] == support.quote


def test_27cf_unanswerable_question_stays_abstained_without_evidence() -> None:
    question = (
        "Are humans and machine learning systems fooled by the same kinds of "
        "illusions?"
    )

    result = _run_boolean(
        question,
        "unanswerable The retrieved context does not establish this.",
        [],
    )

    assert result.answer == ABSTAIN_MESSAGE
    assert result.verify_decision.status == "not_enough_evidence"
    assert result.guardrail_decision.action == "abstain"
    assert "query_plan" not in result.evidence_bundle.metadata or (
        result.evidence_bundle.metadata["query_plan"].get("stage") != "verified"
    )
