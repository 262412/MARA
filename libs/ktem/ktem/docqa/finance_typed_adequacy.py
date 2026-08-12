from __future__ import annotations

from typing import Any

from .calculation_evidence_identity import calculation_evidence_lookup
from .finance_calculation_contract import finance_calculation_authoritative
from .finance_calculation_recovery import (
    missing_required_calculation_slot_ids,
    synchronize_calculation_recovery,
)
from .finance_numeric_answer import finance_numeric_answer
from .query_plan_schema import plan_from_payload, slot_binding_state
from .query_planning import request_planning_question

_FINANCE_DOMAINS = {"finance", "financial", "financebench"}


def ensure_finance_numeric_trace(request: Any, bundle: Any) -> None:
    metadata = getattr(bundle, "metadata", None)
    if not isinstance(metadata, dict):
        return
    domain = str(getattr(request, "verification_domain", "") or "").strip().lower()
    if domain not in _FINANCE_DOMAINS:
        return
    evidence_items = [
        item for item in getattr(bundle, "items", []) or [] if isinstance(item, dict)
    ]
    existing_trace = metadata.get("finance_numeric_trace")
    if isinstance(existing_trace, dict) and existing_trace:
        trace = _refresh_trace_missing_slots(
            request,
            metadata,
            evidence_items,
            existing_trace,
        )
        _synchronize_typed_query_state(request, metadata, evidence_items, trace)
        synchronize_calculation_recovery(request, metadata, trace)
        _synchronize_typed_support(metadata, evidence_items, trace)
        return
    query_plan = dict(metadata.get("query_plan") or {})
    if query_plan and not finance_calculation_authoritative(query_plan):
        return
    result = finance_numeric_answer(
        request_planning_question(request),
        evidence_items,
        query_plan=query_plan,
    )
    if result is not None:
        trace = result.as_trace()
        metadata["finance_numeric_trace"] = trace
        _synchronize_typed_query_state(request, metadata, evidence_items, trace)
        synchronize_calculation_recovery(request, metadata, trace)
        _synchronize_typed_support(metadata, evidence_items, trace)


def _refresh_trace_missing_slots(
    request: Any,
    metadata: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    existing_trace: dict[str, Any],
) -> dict[str, Any]:
    if not missing_required_calculation_slot_ids(metadata):
        return existing_trace
    query_plan = dict(
        existing_trace.get("authoritative_query_plan")
        or metadata.get("query_plan")
        or {}
    )
    result = finance_numeric_answer(
        request_planning_question(request),
        evidence_items,
        query_plan=query_plan,
    )
    if result is None:
        return existing_trace
    trace = result.as_trace()
    metadata["finance_numeric_trace"] = trace
    return trace


def _synchronize_typed_query_state(
    request: Any,
    metadata: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    trace: dict[str, Any],
) -> None:
    authoritative = dict(trace.get("authoritative_query_plan") or {})
    if not authoritative:
        _synchronize_unverified_query_state(request, metadata)
        return
    existing = dict(metadata.get("query_plan") or {})
    bound = dict(metadata.get("bound_query_plan") or {})
    current_version = max(
        _nonnegative_int(getattr(request, "query_plan_state_version", 0)),
        _nonnegative_int(existing.get("state_version")),
        _nonnegative_int(bound.get("state_version")),
        _nonnegative_int(authoritative.get("state_version")),
    )
    payload = dict(authoritative)
    question = request_planning_question(request)
    request_plan = plan_from_payload(
        question,
        answer_type=str(
            getattr(request, "answer_type", None)
            or getattr(request, "task_type", None)
            or payload.get("answer_type")
            or "numeric"
        ),
        verification_domain=str(
            getattr(request, "verification_domain", None)
            or (payload.get("constraints") or {}).get("verification_domain")
            or "finance"
        ),
        payload=payload,
    )
    payload["plan_id"] = request_plan.plan_id
    slot_states = _typed_verification_slot_states(payload, evidence_items, trace)
    changed = (
        _query_plan_signature(existing) != _query_plan_signature(payload)
        or _query_plan_signature(bound) != _query_plan_signature(payload)
        or metadata.get("verification_slot_states") != slot_states
    )
    state_version = current_version + 1 if changed else current_version
    if state_version:
        payload["state_version"] = state_version
    trace["authoritative_query_plan"] = dict(payload)
    metadata["query_plan"] = payload
    metadata["bound_query_plan"] = dict(payload)
    metadata["query_plan_id"] = request_plan.plan_id
    metadata["missing_required_slot_count"] = sum(
        bool(slot.get("required_for_retrieval"))
        and slot_binding_state(slot) != "filled"
        for slot in payload.get("evidence_slots") or []
        if isinstance(slot, dict)
    )
    request.query_plan = request_plan
    request.query_plan_id = request_plan.plan_id
    request.query_plan_state_version = state_version
    metadata["verification_slot_states"] = slot_states


def _synchronize_unverified_query_state(
    request: Any,
    metadata: dict[str, Any],
) -> None:
    existing = dict(metadata.get("query_plan") or {})
    bound = dict(metadata.get("bound_query_plan") or {})
    request_payload = _request_query_plan_payload(request)
    payload = _unverified_query_plan(existing or bound or request_payload, request)
    question = request_planning_question(request)
    request_plan = plan_from_payload(
        question,
        answer_type=str(payload.get("answer_type") or "numeric"),
        verification_domain=str(
            getattr(request, "verification_domain", None)
            or (payload.get("constraints") or {}).get("verification_domain")
            or "finance"
        ),
        payload=payload,
    )
    payload["plan_id"] = request_plan.plan_id
    slot_states = _missing_verification_slot_states(payload)
    current_version = max(
        _nonnegative_int(getattr(request, "query_plan_state_version", 0)),
        _nonnegative_int(existing.get("state_version")),
        _nonnegative_int(bound.get("state_version")),
    )
    changed = (
        _query_plan_signature(existing) != _query_plan_signature(payload)
        or _query_plan_signature(bound) != _query_plan_signature(payload)
        or metadata.get("verification_slot_states") != slot_states
    )
    state_version = current_version + 1 if changed else current_version
    if state_version:
        payload["state_version"] = state_version
    metadata["query_plan"] = dict(payload)
    metadata["bound_query_plan"] = dict(payload)
    metadata["query_plan_id"] = request_plan.plan_id
    metadata["missing_required_slot_count"] = sum(
        bool(slot.get("required_for_retrieval"))
        for slot in payload.get("evidence_slots") or []
        if isinstance(slot, dict)
    )
    metadata["verification_slot_states"] = slot_states
    request.query_plan = request_plan
    request.query_plan_id = request_plan.plan_id
    request.query_plan_state_version = state_version


def _request_query_plan_payload(request: Any) -> dict[str, Any]:
    plan = getattr(request, "query_plan", None)
    as_dict = getattr(plan, "as_dict", None)
    if callable(as_dict):
        return dict(as_dict())
    return dict(plan) if isinstance(plan, dict) else {}


def _unverified_query_plan(
    source: dict[str, Any],
    request: Any,
) -> dict[str, Any]:
    payload = dict(source)
    payload.pop("plan_id", None)
    payload.pop("binding_trace", None)
    payload.pop("verified_required_slot_ids", None)
    payload["answer_type"] = str(
        payload.get("answer_type")
        or getattr(request, "answer_type", None)
        or getattr(request, "task_type", None)
        or "numeric"
    )
    payload["question_type"] = str(payload.get("question_type") or "unplanned_numeric")
    payload["constraints"] = {
        **dict(payload.get("constraints") or {}),
        "verification_domain": str(
            getattr(request, "verification_domain", None) or "finance"
        ),
    }
    payload["state_authority"] = "unverified_calculation.v1"
    payload["evidence_slots"] = [
        _missing_slot(slot)
        for slot in payload.get("evidence_slots") or []
        if isinstance(slot, dict)
    ]
    return payload


def _missing_slot(slot: dict[str, Any]) -> dict[str, Any]:
    missing = dict(slot)
    missing["status"] = "missing"
    missing["evidence_ids"] = []
    return missing


def _missing_verification_slot_states(
    query_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "slot_id": str(slot.get("slot_id") or ""),
            "status": "missing",
            "evidence_ids": [],
        }
        for slot in query_plan.get("evidence_slots") or []
        if isinstance(slot, dict) and bool(slot.get("required_for_verification"))
    ]


def _typed_verification_slot_states(
    query_plan: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    trace: dict[str, Any],
) -> list[dict[str, Any]]:
    verification = dict(trace.get("calculation_verification") or {})
    execution = dict(trace.get("calculation_execution") or {})
    verified_required = {
        str(value).strip()
        for value in verification.get("verified_required_slot_ids") or []
        if str(value or "").strip()
    }
    citation_ids = {
        str(value).strip()
        for value in execution.get("citation_ids") or []
        if str(value or "").strip()
    }
    lookup = calculation_evidence_lookup(evidence_items)
    citations_resolve = bool(citation_ids) and citation_ids <= set(lookup)
    states: list[dict[str, Any]] = []
    for slot in query_plan.get("evidence_slots") or []:
        if not isinstance(slot, dict) or not bool(
            slot.get("required_for_verification")
        ):
            continue
        slot_id = str(slot.get("slot_id") or "").strip()
        raw_evidence_ids = [
            str(value).strip()
            for value in slot.get("evidence_ids") or []
            if str(value or "").strip()
        ]
        evidence_ids = [value for value in raw_evidence_ids if value in lookup]
        all_ids_resolve = bool(raw_evidence_ids) and len(evidence_ids) == len(
            raw_evidence_ids
        )
        verified = (
            slot_id in verified_required
            and all_ids_resolve
            and set(evidence_ids) <= citation_ids
            and citations_resolve
            and verification.get("valid") is True
            and execution.get("status") == "ok"
            and slot_binding_state(
                slot,
                evidence_items,
                materialized=lambda item: _typed_slot_materialized(slot, item),
            )
            == "filled"
        )
        states.append(
            {
                "slot_id": slot_id,
                "status": "verified_support" if verified else "missing",
                "evidence_ids": evidence_ids if verified else [],
            }
        )
    return states


def _query_plan_signature(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"stage", "state_version", "binding_trace"}
    }


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _synchronize_typed_support(
    metadata: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    trace: dict[str, Any],
) -> None:
    verification = dict(trace.get("calculation_verification") or {})
    execution = dict(trace.get("calculation_execution") or {})
    if not verification.get("valid") or execution.get("status") != "ok":
        _clear_typed_support(metadata)
        return
    slot_states = [
        state
        for state in metadata.get("verification_slot_states") or []
        if isinstance(state, dict)
    ]
    if not slot_states or any(
        state.get("status") != "verified_support" for state in slot_states
    ):
        _clear_typed_support(metadata)
        return
    lookup = calculation_evidence_lookup(evidence_items)
    citation_ids = [
        str(value).strip()
        for value in execution.get("citation_ids") or []
        if str(value or "").strip()
    ]
    if not citation_ids:
        _clear_typed_support(metadata)
        return
    support: list[dict[str, Any]] = []
    seen: set[int] = set()
    for evidence_id in citation_ids:
        item = lookup.get(evidence_id)
        if item is None:
            _clear_typed_support(metadata)
            return
        if id(item) in seen:
            continue
        seen.add(id(item))
        support.append(item)
    metadata["typed_calculation_support_evidence"] = support
    metadata["typed_calculation_citation_ids"] = citation_ids


def _clear_typed_support(metadata: dict[str, Any]) -> None:
    metadata.pop("typed_calculation_support_evidence", None)
    metadata.pop("typed_calculation_citation_ids", None)


def typed_calculation_adequacy(
    evidence_metadata: dict[str, Any],
    *,
    domain: str | None,
) -> tuple[str, str]:
    if str(domain or "").strip().lower() not in _FINANCE_DOMAINS:
        return "not_applicable", "non_finance_domain"
    trace = evidence_metadata.get("finance_numeric_trace")
    trace_payload = trace if isinstance(trace, dict) else {}
    query_plan = dict(
        trace_payload.get("authoritative_query_plan")
        or evidence_metadata.get("query_plan")
        or {}
    )
    constraints = dict(query_plan.get("constraints") or {})
    if not finance_calculation_authoritative(query_plan):
        return "not_applicable", "non_numeric_query_plan"
    if constraints.get("finance_formula_status") == "unsupported":
        return "not_applicable", "unsupported_formula"
    if not isinstance(trace, dict):
        return "incomplete", "missing_typed_calculation_trace"
    verification = dict(trace.get("calculation_verification") or {})
    execution = dict(trace.get("calculation_execution") or {})
    if not verification.get("valid") or execution.get("status") != "ok":
        return "incomplete", "typed_calculation_not_verified"
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
    if not required or required != verified:
        return "incomplete", "required_execution_slots_not_verified"
    execution_required = {
        str(slot.get("slot_id") or "").strip()
        for slot in query_plan.get("evidence_slots") or []
        if isinstance(slot, dict)
        and bool(slot.get("required_for_execution"))
        and str(slot.get("slot_id") or "").strip()
    }
    if execution_required and not execution_required.issubset(verified):
        return "incomplete", "query_plan_execution_slots_not_verified"
    evidence = [
        item
        for item in evidence_metadata.get("evidence") or []
        if isinstance(item, dict)
    ]
    if any(
        slot_binding_state(
            slot,
            evidence,
            materialized=lambda item: _typed_slot_materialized(slot, item),
        )
        != "filled"
        for slot in query_plan.get("evidence_slots") or []
        if isinstance(slot, dict) and bool(slot.get("required_for_execution"))
    ):
        return "incomplete", "query_plan_execution_slots_incomplete"
    citation_ids = [
        str(value).strip()
        for value in execution.get("citation_ids") or []
        if str(value or "").strip()
    ]
    evidence_lookup = calculation_evidence_lookup(evidence)
    if not citation_ids or any(value not in evidence_lookup for value in citation_ids):
        return "incomplete", "execution_citation_not_resolvable"
    return "good", "verified_typed_execution"


def _typed_slot_materialized(slot: dict[str, Any], item: dict[str, Any]) -> bool:
    if str(slot.get("role") or "") == "dimension":
        return bool(item.get("scale") or item.get("unit") or item.get("text"))
    if bool(slot.get("required_for_execution")):
        return item.get("value") not in (None, "")
    return bool(item.get("value") or item.get("text") or item.get("ocr_text"))
