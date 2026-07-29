from __future__ import annotations

from typing import Any

from .metrics import is_abstention_answer


def structured_or_text_abstention(
    prediction: dict[str, Any],
    answer: str,
) -> bool:
    for field in (
        "guardrail_decision",
        "verify_decision",
        "retrieve_decision",
        "controller_decision",
    ):
        decision = prediction.get(field)
        if not isinstance(decision, dict):
            continue
        state = " ".join(
            str(decision.get(key) or "").strip().lower()
            for key in ("action", "status", "decision")
        )
        if any(
            marker in state
            for marker in ("abstain", "insufficient", "unanswerable", "blocked")
        ):
            return True
    metadata = prediction.get("evidence_metadata")
    if isinstance(metadata, dict):
        answerability = metadata.get("answerability_contract_trace")
        if isinstance(answerability, dict) and any(
            marker in str(answerability.get(key) or "").strip().lower()
            for key in ("action", "status", "post_contract_answer")
            for marker in ("abstain", "unanswerable", "insufficient")
        ):
            return True
    return is_abstention_answer(answer)
