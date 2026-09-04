from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest


def frozen_projection_complete(
    value: Mapping[str, Any],
    *,
    contract_id: str,
    input_count_key: str,
    attempts_required: bool,
) -> bool:
    trace = dict(value)
    decisions = list(trace.get("decisions") or [])
    attempts = list(trace.get("attempts") or [])
    attempts_complete = bool(
        not attempts_required
        or (
            attempts
            and int(trace.get("attempt_count") or 0) == len(attempts)
            and canonical_digest(attempts) == trace.get("attempts_digest")
        )
    )
    return bool(
        trace.get("contract_id") == contract_id
        and trace.get("complete") is True
        and int(trace.get(input_count_key) or 0) == len(decisions)
        and int(trace.get("decision_count") or 0) == len(decisions)
        and canonical_digest(decisions) == trace.get("decisions_digest")
        and attempts_complete
    )


def candidate_request_projection_complete(
    value: Mapping[str, Any],
    *,
    message_stack: list[Any],
) -> bool:
    projection = dict(value)
    if not frozen_projection_complete(
        projection,
        contract_id="qasper_candidate_request_projection.v1",
        input_count_key="input_record_count",
        attempts_required=True,
    ):
        return False
    decisions = [dict(decision) for decision in projection.get("decisions") or []]
    selected_ids = [
        str(decision.get("evidence_id") or "")
        for decision in decisions
        if decision.get("selected") is True
    ]
    projected_selected_ids = projection.get("selected_record_ids")
    if projected_selected_ids is not None and (
        not isinstance(projected_selected_ids, list)
        or projected_selected_ids != selected_ids
    ):
        return False
    if projection.get("selected_record_count") != len(selected_ids):
        return False
    if projected_selected_ids is not None and projection.get(
        "selected_record_ids_digest"
    ) != canonical_digest(selected_ids):
        return False
    attempts = [dict(attempt) for attempt in projection.get("attempts") or []]
    accepted = attempts[-1]
    if (
        accepted.get("decision") != "accepted"
        or list(accepted.get("record_ids") or []) != selected_ids
    ):
        return False
    final_stack = projection.get("final_message_stack")
    return bool(
        final_stack is None
        or (
            isinstance(final_stack, list)
            and final_stack == message_stack
            and projection.get("final_message_stack_digest")
            == canonical_digest(final_stack)
        )
    )
