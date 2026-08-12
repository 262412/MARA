from __future__ import annotations

from typing import Any

from .query_planning import request_planning_question

_RECOVERY_QUERY_PREFIX = "round2:calculation_recovery:"


def missing_required_calculation_slot_ids(
    evidence_metadata: dict[str, Any],
) -> tuple[str, ...]:
    trace = evidence_metadata.get("finance_numeric_trace")
    if not isinstance(trace, dict):
        return ()
    query_plan = trace.get("authoritative_query_plan")
    verification = trace.get("calculation_verification")
    if not isinstance(query_plan, dict) or not isinstance(verification, dict):
        return ()
    missing = _missing_verification_slot_ids(verification)
    return tuple(
        slot_id
        for slot in query_plan.get("evidence_slots") or []
        if isinstance(slot, dict)
        and str(slot.get("role") or "") == "dimension"
        and bool(slot.get("required_for_execution"))
        and (slot_id := str(slot.get("slot_id") or "").strip()) in missing
    )


def synchronize_calculation_recovery(
    request: Any,
    metadata: dict[str, Any],
    trace: dict[str, Any],
) -> None:
    missing_slot_ids = list(missing_required_calculation_slot_ids(metadata))
    authoritative = dict(trace.get("authoritative_query_plan") or {})
    metadata["missing_required_calculation_slot_ids"] = missing_slot_ids
    metadata["missing_required_slot_count"] = _retrieval_missing_count(
        authoritative
    ) + len(missing_slot_ids)
    recovery = metadata.get("calculation_recovery_trace")
    recovery_trace = dict(recovery) if isinstance(recovery, dict) else None
    if not missing_slot_ids:
        _finalize_recovery(metadata, authoritative, recovery_trace)
        return
    requests = _recovery_requests(
        request,
        metadata,
        authoritative,
        missing_slot_ids,
    )
    _record_pending_recovery(
        metadata,
        authoritative,
        missing_slot_ids,
        requests,
        recovery_trace,
    )


def _missing_verification_slot_ids(verification: dict[str, Any]) -> set[str]:
    missing = {
        str(error).removeprefix("required_slot_missing:").strip()
        for error in verification.get("errors") or []
        if str(error).startswith("required_slot_missing:")
    }
    required = {
        str(value).strip()
        for value in verification.get("required_slot_ids") or []
        if str(value or "").strip()
    }
    verified = {
        str(value).strip()
        for value in verification.get("verified_required_slot_ids") or []
        if str(value or "").strip()
    }
    return missing | (required - verified)


def _retrieval_missing_count(query_plan: dict[str, Any]) -> int:
    return sum(
        bool(slot.get("required_for_retrieval"))
        and str(slot.get("status") or "missing") != "filled"
        for slot in query_plan.get("evidence_slots") or []
        if isinstance(slot, dict)
    )


def _finalize_recovery(
    metadata: dict[str, Any],
    authoritative: dict[str, Any],
    recovery_trace: dict[str, Any] | None,
) -> None:
    _remove_recovery_requests(metadata)
    if recovery_trace is None:
        return
    recovery_trace.update(
        {
            "status": "verified",
            "final_missing_slot_ids": [],
            "authoritative_query_plan_state_authority": str(
                authoritative.get("state_authority") or ""
            ),
            "authoritative_slot_evidence_ids": _authoritative_slot_evidence_ids(
                authoritative
            ),
        }
    )
    metadata["calculation_recovery_trace"] = recovery_trace


def _record_pending_recovery(
    metadata: dict[str, Any],
    authoritative: dict[str, Any],
    missing_slot_ids: list[str],
    requests: list[dict[str, str]],
    recovery_trace: dict[str, Any] | None,
) -> None:
    metadata["calculation_recovery_requests"] = requests
    metadata["second_round_requests"] = _merge_recovery_requests(
        metadata.get("second_round_requests"),
        requests,
    )
    metadata["second_round_queries"] = list(
        dict.fromkeys(
            [
                *(
                    str(value).strip()
                    for value in metadata.get("second_round_queries") or []
                    if str(value or "").strip()
                ),
                *(item["query"] for item in requests),
            ]
        )
    )
    if recovery_trace is None:
        recovery_trace = {
            "contract_id": "calculation_recovery.v1",
            "action": "targeted_retrieval_materialization_rebind",
            "initial_missing_slot_ids": list(missing_slot_ids),
            "attempt_count": 0,
        }
    attempt_count = int(recovery_trace.get("attempt_count") or 0)
    recovery_trace.update(
        {
            "status": "pending" if attempt_count == 0 else "failed",
            "targeted_requests": requests,
            "final_missing_slot_ids": list(missing_slot_ids),
            "authoritative_query_plan_state_authority": str(
                authoritative.get("state_authority") or ""
            ),
            "authoritative_slot_evidence_ids": _authoritative_slot_evidence_ids(
                authoritative
            ),
        }
    )
    metadata["calculation_recovery_trace"] = recovery_trace


def _recovery_requests(
    request: Any,
    metadata: dict[str, Any],
    authoritative: dict[str, Any],
    missing_slot_ids: list[str],
) -> list[dict[str, str]]:
    slots = {
        str(slot.get("slot_id") or ""): slot
        for slot in authoritative.get("evidence_slots") or []
        if isinstance(slot, dict)
    }
    operand_context = _operand_context(metadata, authoritative)
    question = request_planning_question(request)
    return [
        {
            "query_id": f"{_RECOVERY_QUERY_PREFIX}{slot_id}",
            "slot_id": slot_id,
            "query": " ".join(
                dict.fromkeys(
                    value
                    for value in (
                        str(slots.get(slot_id, {}).get("query") or "").strip(),
                        *operand_context,
                        question,
                        "parent table dollars scale unit convention statement locator",
                    )
                    if value
                )
            ),
            "modality": str(slots.get(slot_id, {}).get("modality") or "auto"),
        }
        for slot_id in missing_slot_ids
    ]


def _operand_context(
    metadata: dict[str, Any],
    authoritative: dict[str, Any],
) -> list[str]:
    planned = metadata.get("planned_query_plan")
    planned_slots = planned.get("evidence_slots") if isinstance(planned, dict) else None
    slots = (
        planned_slots
        if isinstance(planned_slots, list)
        else list(authoritative.get("evidence_slots") or [])
    )
    return [
        " ".join(
            str(slot.get(field) or "").strip()
            for field in ("metric", "period", "statement_kind", "query")
            if str(slot.get(field) or "").strip()
        )
        for slot in slots
        if isinstance(slot, dict)
        and str(slot.get("role") or "") == "operand"
        and bool(slot.get("required_for_execution"))
    ]


def _merge_recovery_requests(
    existing: Any,
    recovery: list[dict[str, str]],
) -> list[dict[str, str]]:
    requests = [dict(item) for item in existing or [] if isinstance(item, dict)]
    by_slot = {
        str(item.get("slot_id") or ""): index
        for index, item in enumerate(requests)
        if str(item.get("slot_id") or "")
    }
    for item in recovery:
        slot_id = item["slot_id"]
        if slot_id in by_slot:
            requests[by_slot[slot_id]] = dict(item)
        else:
            by_slot[slot_id] = len(requests)
            requests.append(dict(item))
    return requests


def _remove_recovery_requests(metadata: dict[str, Any]) -> None:
    recovery_requests = metadata.pop("calculation_recovery_requests", [])
    targeted_queries = {
        str(item.get("query") or "")
        for item in recovery_requests or []
        if isinstance(item, dict)
    }
    requests = metadata.get("second_round_requests")
    if isinstance(requests, list):
        metadata["second_round_requests"] = [
            item
            for item in requests
            if not (
                isinstance(item, dict)
                and str(item.get("query_id") or "").startswith(_RECOVERY_QUERY_PREFIX)
            )
        ]
    queries = metadata.get("second_round_queries")
    if isinstance(queries, list):
        metadata["second_round_queries"] = [
            query for query in queries if str(query) not in targeted_queries
        ]


def _authoritative_slot_evidence_ids(
    query_plan: dict[str, Any],
) -> dict[str, list[str]]:
    return {
        slot_id: [
            str(value).strip()
            for value in slot.get("evidence_ids") or []
            if str(value or "").strip()
        ]
        for slot in query_plan.get("evidence_slots") or []
        if isinstance(slot, dict)
        and bool(slot.get("required_for_execution"))
        and (slot_id := str(slot.get("slot_id") or "").strip())
    }
