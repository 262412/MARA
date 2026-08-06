from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from benchmark.qasper_answerability import verify_qasper_answerability


class _VerifierLLM:
    def __init__(self, payload: dict[str, str]):
        self.payload = payload

    def __call__(self, _prompt: str, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(text=json.dumps(self.payload))


def _item(local_id: str, text: str, **metadata: Any) -> dict[str, Any]:
    return {
        "source_id": "paper",
        "evidence_id": local_id,
        "text": text,
        **metadata,
    }


def test_english_topic_without_result_relation_cannot_override_candidate():
    current = _item(
        "current",
        (
            "As a main field of interest in the current study, we identified "
            "controversial topics in education in English-speaking countries."
        ),
    )
    related = _item(
        "related",
        "Goudas et al. 2014 evaluated user-generated Greek texts.",
        section_id="related_work",
    )
    result = verify_qasper_answerability(
        _VerifierLLM(
            {
                "verdict": "insufficient_evidence",
                "evidence_quote": "",
            }
        ),
        question="Do they report results only on English data?",
        evidence=f"{current['text']}\n{related['text']}",
        evidence_items=[related, current],
        candidate_answer="no",
    )

    assert result.answer == "unanswerable"
    assert result.trace["verdict"] == "insufficient_evidence"
    assert result.trace["reason"] == "insufficient_evidence"
    assert result.trace["verifier_input_evidence_ids"] == (
        "evidence:paper:current,evidence:paper:related"
    )
    assert result.trace["verifier_dropped_evidence_ids"] == ""
    assert int(result.trace["verifier_input_character_count"]) > 0
    assert int(result.trace["verifier_input_token_count"]) > 0
    assert result.trace["verifier_budget_exhausted"] == "false"
