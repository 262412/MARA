from __future__ import annotations

from typing import Any

from .metrics import is_abstention_answer


def structured_or_text_abstention(
    prediction: dict[str, Any],
    answer: str,
) -> bool:
    terminal_contract_state = _terminal_task_contract_abstention(prediction, answer)
    if terminal_contract_state is not None:
        return terminal_contract_state
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


def _terminal_task_contract_abstention(
    prediction: dict[str, Any],
    answer: str,
) -> bool | None:
    contract = prediction.get("task_answer_contract")
    if not isinstance(contract, dict) or contract.get("status") != "applied":
        return None
    verification = prediction.get("post_contract_verification")
    if not isinstance(verification, dict):
        return None
    terminal_answer = str(verification.get("answer") or "").strip()
    if not terminal_answer or _normalized(terminal_answer) != _normalized(answer):
        return None
    return is_abstention_answer(terminal_answer)


def _normalized(value: str) -> str:
    normalized = " ".join(str(value or "").strip().lower().split())
    return {
        "true": "yes",
        "false": "no",
    }.get(normalized, normalized)
