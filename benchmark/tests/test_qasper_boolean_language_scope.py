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


def test_closed_english_scope_uses_same_item_corpus_context_across_sections():
    decisive = (
        "In cooperation with education researchers, we identified current "
        "controversial topics in education in English-speaking countries."
    )
    current = _item(
        "current",
        (
            "This section describes our data selection, annotation, and evaluation "
            "process for creating a new corpus. "
            "The overview is intentionally detailed for reproducibility. "
            "The project covers a broad range of perspectives. "
            + decisive
            + " We included four registers in the collection. "
            "The registers cover several kinds of user-generated content. "
            "Given the selected topics and registers, we compiled a collection of "
            "plain-text documents called the raw corpus."
        ),
        section_id="methods",
    )

    result = verify_qasper_answerability(
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("deterministic closed-scope evidence must bypass the model")
        ),
        question="Do they report results only on English data?",
        evidence=current["text"],
        evidence_items=[current],
        candidate_answer="no",
    )

    assert result.answer == "yes"
    assert result.trace["parser_status"] == "not_called_deterministic_scope"
    assert result.trace["evidence_quote"] == decisive
