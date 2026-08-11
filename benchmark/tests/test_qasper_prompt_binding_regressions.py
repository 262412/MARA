from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa.boolean_proposition_evidence import _object_compatibility
from ktem.docqa.boolean_relations import (
    boolean_relation_lemmas,
    boolean_relations_align,
)
from ktem.docqa.query_phrase_extraction import semantic_boolean_proposition_question

from benchmark.qasper_answerability import verify_qasper_answerability
from benchmark.qasper_prompt_budget import (
    _ranked_evidence_records,
    fit_qasper_verifier_items,
)


class _Verifier:
    def __init__(self, responses: list[dict[str, str]]) -> None:
        self.responses = [json.dumps(response) for response in responses]
        self.calls: list[str] = []

    def __call__(self, prompt: str, **_kwargs: Any) -> Any:
        self.calls.append(prompt)
        return SimpleNamespace(text=self.responses.pop(0))


def _item(evidence_id: str, text: str) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "results",
        "text": text,
    }


def _prompt(evidence: str) -> str:
    return f"QUESTION\n\nEVIDENCE\n{evidence}\n\nJSON"


@pytest.mark.parametrize(
    "question",
    (
        "Overall, does the method improve accuracy?",
        "Background; should the method improve accuracy?",
        "Background: may the method improve accuracy?",
        "Background; might the method improve accuracy?",
    ),
)
def test_authoritative_boolean_detector_controls_long_evidence_packing(
    question: str,
) -> None:
    target = "The method improves accuracy on the evaluation corpus."
    long_text = " ".join(["Irrelevant background sentence."] * 260 + [target])

    prompt, bounded, trace = fit_qasper_verifier_items(
        [_item("support", long_text)],
        _prompt,
        question=question,
        candidate_answer="yes",
    )

    assert target in bounded
    assert len(bounded) < len(long_text)
    assert len(prompt) <= 7000
    assert trace["verifier_input_evidence_refs"] == "E1:S1"


def test_boolean_packing_uses_one_exact_continuous_three_sentence_window() -> None:
    target = (
        "We use parallel data. "
        "This improves semantic role induction. "
        "The gains hold across multiple languages."
    )
    long_text = " ".join(
        ["Unrelated background sentence."] * 80
        + [target]
        + ["Unrelated appendix sentence."] * 80
    )
    question = (
        "Overall, does having parallel data improve semantic role induction "
        "across multiple languages?"
    )

    prompt, bounded, trace = fit_qasper_verifier_items(
        [_item("support", long_text)],
        _prompt,
        question=question,
        candidate_answer="yes",
    )

    mapping = json.loads(trace["verifier_evidence_alias_mapping"])
    assert len(mapping) == 1
    start = mapping[0]["item_span_start"]
    end = mapping[0]["item_span_end"]
    packed_text = bounded.split("\n", 1)[1]
    assert packed_text == long_text[start:end]
    assert packed_text == target
    assert len(prompt) <= 7000


def test_boolean_proposition_priority_precedes_generic_claim_priority() -> None:
    question = "Did the method improve accuracy?"
    generic = _item(
        "generic",
        "The candidate rationale discusses the method and its accuracy.",
    )
    proposition = _item("proposition", "The method improved accuracy.")

    rows = _ranked_evidence_records(
        [generic, proposition],
        question=question,
        candidate_answer="yes",
        required=set(),
        priority=set(),
        claim_support={"generic"},
        claim_contradiction=set(),
    )

    assert rows[0].source_text == proposition["text"]


@pytest.mark.parametrize("alias", ("improve", "benefit", "enhance", "increase"))
def test_improvement_relation_aliases_share_one_relation(alias: str) -> None:
    assert boolean_relation_lemmas(alias) == {"improve"}
    assert boolean_relations_align(
        "Does parallel data improve semantic role induction?",
        f"Parallel data can {alias} semantic role induction.",
    )


def test_parallel_data_and_parallel_corpus_are_narrow_object_aliases() -> None:
    score, _object = _object_compatibility(
        "Does parallel data improve semantic role induction?",
        "The parallel corpus enhances semantic role induction.",
    )

    assert score == 1.0


def test_boolean_framework_words_do_not_pollute_proposition_semantics() -> None:
    semantic = semantic_boolean_proposition_question(
        "Overall, does having parallel data improve semantic role induction "
        "across multiple languages?"
    ).lower()

    assert "overall" not in semantic
    assert "having" not in semantic
    assert "across multiple" not in semantic
    assert "parallel data" in semantic
    assert "multiple languages" in semantic


def test_quote_mismatch_gets_one_repair_before_boolean_adjudication() -> None:
    quote = "The method improved accuracy on the evaluation corpus."
    verifier = _Verifier(
        [
            {
                "verdict": "yes_complete",
                "evidence_ref": "E1:S1",
                "evidence_quote": "The method achieved better results.",
            },
            {
                "verdict": "yes_complete",
                "evidence_ref": "E1:S1",
                "evidence_quote": quote,
            },
        ]
    )

    result = verify_qasper_answerability(
        verifier,
        question="Did the method improve accuracy?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("support", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "yes"
    assert len(verifier.calls) == 2
    assert result.trace["repair_attempted"] == "true"
    assert result.trace["quote_ref_validation_status"] == "bound"


def test_out_of_buffer_ref_gets_one_repair_then_unique_canonical_rebind() -> None:
    quote = "The method improved accuracy on the evaluation corpus."
    verifier = _Verifier(
        [
            {
                "verdict": "yes_complete",
                "evidence_ref": "E9:S1",
                "evidence_quote": quote,
            },
            {
                "verdict": "yes_complete",
                "evidence_ref": "E9:S1",
                "evidence_quote": quote,
            },
        ]
    )

    result = verify_qasper_answerability(
        verifier,
        question="Did the method improve accuracy?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("support", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "yes"
    assert len(verifier.calls) == 2
    assert result.trace["evidence_ref"] == "E1:S1"
    assert result.trace["quote_ref_validation_status"] == "evidence_ref_rebound"


def test_ambiguous_quote_is_rejected_after_at_most_two_verifier_calls() -> None:
    quote = "The method improved accuracy."
    evidence = f"{quote} Additional details follow. {quote}"
    verifier = _Verifier(
        [
            {
                "verdict": "yes_complete",
                "evidence_ref": "E1:S1",
                "evidence_quote": quote,
            },
            {
                "verdict": "yes_complete",
                "evidence_ref": "E1:S1",
                "evidence_quote": quote,
            },
        ]
    )

    result = verify_qasper_answerability(
        verifier,
        question="Did the method improve accuracy?",
        answer_type="boolean",
        evidence=evidence,
        evidence_items=[_item("support", evidence)],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert len(verifier.calls) == 2
    assert result.trace["repair_status"] == "error"
