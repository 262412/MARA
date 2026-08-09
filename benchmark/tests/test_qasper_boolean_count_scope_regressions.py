from __future__ import annotations

import json
from typing import Any

from benchmark.qasper_answerability import verify_qasper_answerability


class _Verifier:
    def __init__(self, verdict: str, quote: str, evidence_ref: str) -> None:
        self.response = json.dumps(
            {
                "verdict": verdict,
                "evidence_ref": evidence_ref,
                "evidence_quote": quote,
            }
        )

    def __call__(self, _prompt: str, **_kwargs: Any) -> Any:
        return type("Result", (), {"text": self.response})()


def _item(evidence_id: str, text: str) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "results",
        "text": text,
    }


def test_count_scope_ignores_topic_language_and_abbreviation_tokens() -> None:
    quote = (
        "The CreateDebate dataset was collected from an English online debate "
        "forum discussing four topics: abortion (ABO), gay rights (GAY), "
        "Obama (OBA), and marijuana (MAR)."
    )

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question="Did they collect the two datasets?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("create-debate", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "quantified_object_scope_incomplete"
    assert result.trace["evidence_ref"] == "E1:S1"
    assert result.trace["evidence_quote"] == quote
    assert result.trace["boolean_scope_reason"] == "quantified_object_scope_incomplete"


def test_count_scope_accepts_coordinated_all_caps_dataset_names() -> None:
    quote = "The MNLI and SNLI datasets were evaluated."

    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E1:S1"),
        question="Did they evaluate the two datasets?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("coordinated-acronyms", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "yes"
    assert result.trace["boolean_scope_reason"] == "quantified_object_scope_complete"
