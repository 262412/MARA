from __future__ import annotations

from typing import Any

from kotaemon.base import HumanMessage, SystemMessage

from .mara_qasper_candidate_budget import (
    QASPER_CANDIDATE_INPUT_TOKEN_BUDGET,
    candidate_drop_index,
    candidate_input_token_measurement,
)
from .mara_qasper_candidate_evidence import candidate_evidence_set_binding
from .mara_qasper_candidate_identity import candidate_digest
from .mara_qasper_candidate_prompt import _bound_candidate_slots, _candidate_prompt

_CandidateRequestFit = tuple[
    list[dict[str, Any]],
    dict[str, Any],
    list[Any],
    dict[str, Any],
    int,
]

_SYSTEM_PROMPT = (
    "You are the sole answer-candidate generator for a QASPER Boolean question. "
    "Use only the typed question proposition and labeled retrieved evidence. "
    "Return exactly one structured "
    "candidate: yes, no, or unanswerable. Prefer proposition- and slot-aligned "
    "evidence when deciding the candidate: use yes for proposition support, no "
    "for an explicit contradiction, and unanswerable only when neither is present. "
    "Candidate parsing is format-only; "
    "verification uncertainty is handled later by the verifier. Do not "
    "include explanation, citations, or an alternative answer."
)

_CONTRACT_PROBE_SYSTEM_PROMPT = (
    "You are exercising the QASPER candidate transport contract. Preserve the "
    "supplied original candidate exactly. Do not answer the question or change "
    "the candidate after reading the audit context. Return only the required "
    "structured candidate object."
)


def candidate_messages(
    question: str,
    evidence: list[dict[str, Any]],
    evidence_diagnostics: dict[str, Any],
    *,
    controlled_candidate: str,
) -> list[Any]:
    audit_context = _candidate_prompt(
        question,
        evidence,
        proposition=evidence_diagnostics.get("typed_proposition"),
        proposition_resolution=evidence_diagnostics.get(
            "question_proposition_resolution"
        ),
        required_slots=evidence_diagnostics.get("required_slots", []),
        evidence_set_binding=evidence_diagnostics.get("candidate_evidence_set_binding"),
    )
    if not controlled_candidate:
        return [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=audit_context),
        ]
    return [
        SystemMessage(content=_CONTRACT_PROBE_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                "/no_think\nCONTROLLED ORIGINAL CANDIDATE UNDER AUDIT:\n"
                f"{controlled_candidate}\n\nAUDIT CONTEXT (DO NOT RE-ANSWER):\n"
                f"{audit_context}"
            )
        ),
    ]


def fit_candidate_request(
    llm: Any | None,
    question: str,
    evidence: list[dict[str, Any]],
    evidence_diagnostics: dict[str, Any],
    *,
    response_schema: dict[str, Any],
    controlled_candidate: str,
    candidate_transaction_id: str = "",
) -> _CandidateRequestFit:
    initial = list(evidence)
    selected = list(evidence)
    attempts: list[dict[str, Any]] = []
    dropped_count = 0
    pre_request_dropped_count = int(
        evidence_diagnostics.get("pre_request_dropped_evidence_count") or 0
    )
    while True:
        diagnostics, messages, token_measurement = _candidate_request_iteration(
            llm,
            question,
            selected,
            evidence_diagnostics,
            response_schema=response_schema,
            controlled_candidate=controlled_candidate,
            candidate_transaction_id=candidate_transaction_id,
            dropped_count=dropped_count,
            pre_request_dropped_count=pre_request_dropped_count,
        )
        decision, drop_index = _request_fit_decision(token_measurement, selected)
        attempts.append(
            _candidate_request_attempt(
                selected,
                token_measurement,
                decision=decision,
                dropped_evidence_id=(
                    str(selected[drop_index].get("evidence_id") or "")
                    if drop_index is not None
                    else ""
                ),
            )
        )
        if drop_index is None:
            _record_candidate_request_projection(
                diagnostics,
                initial=initial,
                selected=selected,
                attempts=attempts,
            )
            return (
                selected,
                diagnostics,
                messages,
                token_measurement,
                pre_request_dropped_count + dropped_count,
            )
        selected.pop(drop_index)
        dropped_count += 1


def _candidate_request_iteration(
    llm: Any | None,
    question: str,
    selected: list[dict[str, Any]],
    evidence_diagnostics: dict[str, Any],
    *,
    response_schema: dict[str, Any],
    controlled_candidate: str,
    candidate_transaction_id: str,
    dropped_count: int,
    pre_request_dropped_count: int,
) -> tuple[dict[str, Any], list[Any], dict[str, Any]]:
    evidence_set_binding = candidate_evidence_set_binding(
        selected,
        question,
        candidate_transaction_id=candidate_transaction_id,
    )
    bound_slots = _bound_candidate_slots(
        evidence_diagnostics.get("required_slots", []),
        selected,
        binding=evidence_set_binding,
    )
    diagnostics = candidate_request_diagnostics(
        evidence_diagnostics,
        bound_slots,
        evidence_set_binding,
        dropped_count=dropped_count,
        pre_request_dropped_count=pre_request_dropped_count,
    )
    messages = candidate_messages(
        question,
        selected,
        diagnostics,
        controlled_candidate=controlled_candidate,
    )
    token_measurement = candidate_input_token_measurement(
        llm,
        messages,
        response_schema,
    )
    return diagnostics, messages, token_measurement


def _request_fit_decision(
    token_measurement: dict[str, Any],
    selected: list[dict[str, Any]],
) -> tuple[str, int | None]:
    if token_measurement.get("tokenizer_failed"):
        return "tokenizer_failed", None
    if (
        token_measurement["estimated_input_tokens"]
        <= QASPER_CANDIDATE_INPUT_TOKEN_BUDGET
        or not selected
    ):
        return "accepted", None
    drop_index = candidate_drop_index(selected)
    if drop_index is None:
        return "no_eligible_drop", None
    return "drop_record_for_token_budget", drop_index


def _candidate_request_attempt(
    selected: list[dict[str, Any]],
    token_measurement: dict[str, Any],
    *,
    decision: str,
    dropped_evidence_id: str = "",
) -> dict[str, Any]:
    return {
        "record_ids": [str(record.get("evidence_id") or "") for record in selected],
        "estimated_input_tokens": int(
            token_measurement.get("estimated_input_tokens") or 0
        ),
        "tokenizer_failed": token_measurement.get("tokenizer_failed") is True,
        "decision": decision,
        "dropped_evidence_id": dropped_evidence_id,
    }


def _record_candidate_request_projection(
    diagnostics: dict[str, Any],
    *,
    initial: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
) -> None:
    selected_ids = {str(record.get("evidence_id") or "") for record in selected}
    decisions = [
        {
            "evidence_id": str(record.get("evidence_id") or ""),
            "selected": str(record.get("evidence_id") or "") in selected_ids,
            "decision": (
                "selected_for_model_request"
                if str(record.get("evidence_id") or "") in selected_ids
                else "candidate_request_token_budget"
            ),
        }
        for record in initial
    ]
    diagnostics["candidate_request_projection_trace"] = {
        "contract_id": "qasper_candidate_request_projection.v1",
        "complete": True,
        "input_record_count": len(initial),
        "selected_record_count": len(selected),
        "decision_count": len(decisions),
        "decisions_digest": _digest(decisions),
        "decisions": decisions,
        "attempt_count": len(attempts),
        "attempts_digest": _digest(attempts),
        "attempts": attempts,
    }


def candidate_request_diagnostics(
    evidence_diagnostics: dict[str, Any],
    bound_slots: list[dict[str, Any]],
    evidence_set_binding: dict[str, Any],
    *,
    dropped_count: int,
    pre_request_dropped_count: int,
) -> dict[str, Any]:
    return {
        **evidence_diagnostics,
        "required_slots": bound_slots,
        "candidate_evidence_set_binding": evidence_set_binding,
        "candidate_request_dropped_evidence_count": dropped_count,
        "request_dropped_evidence_count": pre_request_dropped_count + dropped_count,
        "evidence_dropped_count": (
            int(evidence_diagnostics.get("evidence_dropped_count") or 0) + dropped_count
        ),
    }


_digest = candidate_digest
