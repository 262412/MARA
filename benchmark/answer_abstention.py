from __future__ import annotations

from typing import Any

from .finance_citation_contract import clear_answer_citation_state
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


def apply_abstention_projection(
    prediction: dict[str, Any],
    *,
    answer_for_user: str,
    answer_for_scoring: str,
    answer_text_for_user: str,
    presentation_answer: str,
    source: str,
    preserve_semantic_answer: bool,
) -> tuple[str, str, str]:
    terminal_abstention = structured_or_text_abstention(
        prediction, answer_text_for_user
    )
    presentation_abstention = bool(
        preserve_semantic_answer
        and structured_or_text_abstention(prediction, presentation_answer)
    )
    if not (terminal_abstention or presentation_abstention):
        prediction["answer_status"] = "answered"
        return answer_for_user, answer_for_scoring, source
    if not preserve_semantic_answer:
        answer_for_scoring = "unanswerable"
        source = "canonical_abstention"
    prediction["answer_status"] = "abstained"
    clear_answer_citation_state(prediction)
    return (
        presentation_answer if presentation_abstention else answer_text_for_user,
        answer_for_scoring,
        source,
    )


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
