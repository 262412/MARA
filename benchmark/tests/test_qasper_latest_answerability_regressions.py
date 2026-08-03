from types import SimpleNamespace
from typing import Any

import pytest

from benchmark.qasper_answerability import verify_qasper_answerability
from benchmark.qasper_boolean import boolean_candidate_polarity


class _VerifierLLM:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, prompt: str, **kwargs):
        self.calls.append((prompt, kwargs))
        if len(prompt) > 7000:
            raise RuntimeError("verifier prompt exceeds the local model budget")
        return SimpleNamespace(text=self.response)


@pytest.mark.parametrize(
    ("candidate", "expected"),
    (
        ("Yes.", "yes"),
        ("No, the paper does not report that experiment.", "no"),
        ("Answer: yes", "yes"),
        ("yes\nThe cited passage establishes the result.", "yes"),
        ("The evidence is mixed and no polarity is explicit.", ""),
    ),
)
def test_boolean_candidate_parser_is_conservative(
    candidate: str,
    expected: str,
) -> None:
    assert boolean_candidate_polarity(candidate) == expected


def test_manifest_boolean_type_routes_verbose_candidate_through_typed_adjudication():
    quote = "The authors did not release the code with the paper."
    llm = _VerifierLLM('{"verdict":"no_complete","evidence_quote":' f'"{quote}"}}')

    result = verify_qasper_answerability(
        llm,
        question="Did the authors release the code?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[{"source_id": "paper", "span_id": "release", "text": quote}],
        candidate_answer=(
            "Yes.\nThe retrieved material appears to discuss a public release."
        ),
    )

    assert result.answer == "no"
    assert result.trace["raw_verifier_verdict"] == "no_complete"
    assert result.trace["authoritative_quote_evidence_id"] == "span:paper:release"


def test_quality_control_partial_yes_is_corrected_by_quote_scoped_relation():
    quote = (
        "It is much harder to validate the quality of such data at such a "
        "scale and such varying levels of complexity."
    )
    llm = _VerifierLLM('{"verdict":"yes_partial","evidence_quote":' f'"{quote}"}}')

    result = verify_qasper_answerability(
        llm,
        question="Are the automatically constructed datasets subject to quality control?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[{"source_id": "paper", "span_id": "quality", "text": quote}],
        candidate_answer=(
            "Yes\nThe evidence discusses validation and therefore appears to "
            "describe quality control."
        ),
    )

    assert result.answer == "no"
    assert result.trace["reason"] == "grounded_complete_proposition"
    assert result.trace["authoritative_quote_evidence_id"] == "span:paper:quality"


@pytest.mark.parametrize(
    ("question", "quote", "verdict", "expected"),
    (
        (
            "Is pre-training effective in their evaluation?",
            (
                "The encoder-decoder-reconstructor can not be trained well without "
                "pre-training, so it proves that we have to train the forward "
                "translation model as pre-training."
            ),
            "yes_complete",
            "yes",
        ),
        (
            "Does RoBERTa outperform BERT?",
            "We also observe that XLNet consistently outperforms BERT and RoBERTa.",
            "no_complete",
            "no",
        ),
    ),
)
def test_complete_semantic_verdict_is_not_reversed_by_lexical_polarity(
    question: str,
    quote: str,
    verdict: str,
    expected: str,
) -> None:
    llm = _VerifierLLM(
        '{"verdict":"' + verdict + '","evidence_quote":"' + quote + '"}'
    )

    result = verify_qasper_answerability(
        llm,
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[{"source_id": "paper", "span_id": "claim", "text": quote}],
        candidate_answer="no" if expected == "yes" else "yes",
    )

    assert result.answer == expected
    assert result.trace["raw_verifier_verdict"] == verdict
    assert result.trace["authoritative_quote_evidence_id"] == "span:paper:claim"


def test_quality_control_partial_quote_uses_unique_explicit_relation_support():
    verifier_quote = (
        "We find automatically constructing probes to be vulnerable to annotation "
        "artifacts, which we carefully control for."
    )
    authoritative_quote = (
        "It is much harder to validate the quality of such data at such a scale "
        "and such varying levels of complexity."
    )
    item_text = f"{verifier_quote} {authoritative_quote}"
    llm = _VerifierLLM(
        '{"verdict":"yes_partial","evidence_quote":"'
        + verifier_quote
        + '"}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Are the automatically constructed datasets subject to quality control?",
        answer_type="boolean",
        evidence=item_text,
        evidence_items=[
            {"source_id": "paper", "span_id": "quality-page", "text": item_text}
        ],
        candidate_answer=(
            "Yes. The datasets are carefully controlled for annotation artifacts."
        ),
    )

    assert result.answer == "no"
    assert result.trace["raw_verifier_verdict"] == "yes_partial"
    assert result.trace["evidence_quote"] == authoritative_quote
    assert result.trace["authoritative_quote_evidence_id"] == (
        "span:paper:quality-page"
    )


def test_free_text_prompt_reserves_budget_for_every_required_identity():
    required_a = {
        "source_id": "paper",
        "span_id": "required-a",
        "text": ("Background about prior systems. " * 180)
        + "The proposed method reaches 99.53 percent accuracy.",
    }
    required_b = {
        "source_id": "paper",
        "span_id": "required-b",
        "text": ("Detailed comparison appendix. " * 180)
        + "The authors describe this as a benchmark result against the literature.",
    }
    llm = _VerifierLLM(
        '{"verdict":"supported","evidence_quote":'
        '"The authors describe this as a benchmark result against the literature.",'
        '"revised_answer":""}'
    )

    result = verify_qasper_answerability(
        llm,
        question="How do their results compare to state-of-the-art?",
        evidence="",
        evidence_items=[required_a, required_b],
        required_evidence_ids=["span:paper:required-a", "span:paper:required-b"],
        candidate_answer="The results compare favorably to state-of-the-art. " * 180,
    )

    assert len(llm.calls[0][0]) <= 7000
    assert result.trace["verifier_required_evidence_coverage"] == "1.000000"
    assert set(result.trace["verifier_input_evidence_ids"].split(",")) == {
        "span:paper:required-a",
        "span:paper:required-b",
    }
    assert "span_start" in result.trace["verifier_input_evidence_spans"]
