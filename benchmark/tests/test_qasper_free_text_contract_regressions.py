from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.qasper_answerability import verify_qasper_answerability


class _VerifierLLM:
    def __init__(self, payload: dict[str, str]):
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def __call__(self, _prompt: str, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(text=json.dumps(self.payload))


def test_question_restatement_cannot_mask_missing_answer_terms():
    quote = (
        "We bridge the gap between normative argumentation theories and "
        "argumentation phenomena encountered in actual data by adapting an "
        "argumentation model tested in an extensive annotation study."
    )
    result = verify_qasper_answerability(
        _VerifierLLM(
            {
                "verdict": "supported_with_pruning",
                "evidence_quote": quote,
                "revised_answer": "refutations in the data",
            }
        ),
        question=(
            "What argumentation phenomena encountered in actual data are now "
            "accounted for by this work?"
        ),
        evidence=quote,
        candidate_answer=(
            "The work accounts for rhetorical questions and figurative language. "
            "It also accounts for refutations in the data."
        ),
    )

    assert result.answer == "unanswerable"
    assert result.trace["verdict"] == "unsupported"


def test_free_text_verifier_binds_positive_quote_to_stable_ref() -> None:
    quote = "The classification model uses labeled features."
    support = {
        "source_id": "paper",
        "span_id": "support",
        "canonical_start": 100,
        "canonical_end": 100 + len(quote),
        "text": quote,
    }

    llm = _VerifierLLM(
        {
            "verdict": "supported",
            "evidence_ref": "E1:S1",
            "evidence_quote": quote,
            "revised_answer": "",
        }
    )
    result = verify_qasper_answerability(
        llm,
        question="What features does the classification model use?",
        evidence=quote,
        evidence_items=[support],
        candidate_answer="labeled features",
    )

    assert result.answer == "labeled features"
    assert result.trace["evidence_ref"] == "E1:S1"
    assert llm.calls[0]["temperature"] == 0
    assert llm.calls[0]["top_p"] == 1
    assert llm.calls[0]["seed"] == 20260724
    assert result.trace["generation_top_p"] == "1"


def test_free_text_verifier_rejects_ref_quote_mismatch() -> None:
    quote = "The classification model uses labeled features."
    distractor = "The appendix lists optimizer settings."

    result = verify_qasper_answerability(
        _VerifierLLM(
            {
                "verdict": "supported",
                "evidence_ref": "E2:S1",
                "evidence_quote": quote,
                "revised_answer": "",
            }
        ),
        question="What features does the classification model use?",
        evidence=f"{quote} {distractor}",
        evidence_items=[
            {
                "source_id": "paper",
                "span_id": "support",
                "canonical_start": 0,
                "canonical_end": len(quote),
                "text": quote,
            },
            {
                "source_id": "paper",
                "span_id": "distractor",
                "canonical_start": 100,
                "canonical_end": 100 + len(distractor),
                "text": distractor,
            },
        ],
        candidate_answer="labeled features",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] == "evidence_ref_quote_mismatch"
    assert result.trace.get("evidence_ref", "") == ""
    assert result.trace.get("evidence_quote", "") == ""


def test_terminal_punctuation_does_not_create_stale_verifier_state():
    decision = {
        "mode": "strict",
        "status": "supported",
        "action": "return",
        "claims": ["labeled features"],
    }
    prediction = {
        "predicted_answer": "Labeled features.",
        "answer_for_scoring": "Labeled features",
        "pre_contract_verification": {"verify_decision": {"status": "unsupported"}},
        "post_contract_verification": {
            "answer": "Labeled features.",
            "verify_decision": decision,
        },
        "verify_decision": decision,
        "evidence_metadata": {
            "verify_decision": decision,
            "answer_dependent_state": "post_contract_verified",
        },
    }

    summary = contract_invariant_summary([prediction])

    assert summary["qasper_stale_verifier_state_count"] == 0.0
