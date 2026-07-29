from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.qasper_answerability import verify_qasper_answerability


class _VerifierLLM:
    def __init__(self, payload: dict[str, str]):
        self.payload = payload

    def __call__(self, _prompt: str, **_kwargs: Any) -> SimpleNamespace:
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
