from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .metrics import is_abstention_answer
from .terminal_answer_state import TERMINAL_ANSWER_STATE, rebuild_terminal_answer_state

ClearCitations = Callable[[dict[str, Any], dict[str, Any]], None]
VerifyAnswer = Callable[[dict[str, Any], dict[str, Any], str], None]
BindSupport = Callable[..., None]


def synchronize_terminal_answer_state(
    prediction: dict[str, Any],
    *,
    clear_citations: ClearCitations,
    verify_answer: VerifyAnswer,
    bind_support: BindSupport,
) -> bool:
    """Commit one authoritative QASPER state after presentation finalization."""

    contract = prediction.get("task_answer_contract")
    if not isinstance(contract, dict) or not str(
        contract.get("contract_id") or ""
    ).startswith("qasper_answerability"):
        return False
    metadata = prediction.setdefault("evidence_metadata", {})
    trace = metadata.get("qasper_answerability")
    if not isinstance(trace, dict):
        return False
    answer = str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    ).strip()
    rendered_citations = [
        dict(item)
        for item in prediction.get("structured_citations") or []
        if isinstance(item, dict)
    ]
    clear_citations(prediction, metadata)
    verify_answer(prediction, metadata, answer)
    bind_support(prediction, metadata, answer=answer, trace=trace)
    decision = dict(prediction.get("verify_decision") or {})
    abstained = is_abstention_answer(answer)
    guardrail = {
        "status": "not_enough_evidence" if abstained else "ok",
        "action": "abstain" if abstained else "return",
        "reason": (
            "Terminal answer has insufficient evidence."
            if abstained
            else "Terminal answer passed post-contract verification."
        ),
    }
    rebuild_terminal_answer_state(
        prediction,
        answer=answer,
        verify_decision=decision,
        claim_verification=dict(prediction.get("claim_verification") or {}),
        supporting_evidence=[
            dict(item)
            for item in metadata.get("verified_claim_support_evidence") or []
            if isinstance(item, dict)
        ],
        guardrail_decision=guardrail,
        emitted_citations=[] if abstained else rendered_citations,
    )
    metadata["answer_dependent_state"] = TERMINAL_ANSWER_STATE
    return True
