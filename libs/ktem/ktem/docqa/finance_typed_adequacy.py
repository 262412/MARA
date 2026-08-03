from __future__ import annotations

from typing import Any

from .calculation_evidence_identity import calculation_evidence_lookup
from .finance_calculation_contract import finance_calculation_authoritative
from .finance_numeric_answer import finance_numeric_answer
from .query_planning import request_planning_question

_FINANCE_DOMAINS = {"finance", "financial", "financebench"}


def ensure_finance_numeric_trace(request: Any, bundle: Any) -> None:
    metadata = getattr(bundle, "metadata", None)
    if not isinstance(metadata, dict) or metadata.get("finance_numeric_trace"):
        return
    domain = str(getattr(request, "verification_domain", "") or "").strip().lower()
    if domain not in _FINANCE_DOMAINS:
        return
    query_plan = dict(metadata.get("query_plan") or {})
    if query_plan and not finance_calculation_authoritative(query_plan):
        return
    evidence_items = [
        item for item in getattr(bundle, "items", []) or [] if isinstance(item, dict)
    ]
    result = finance_numeric_answer(
        request_planning_question(request),
        evidence_items,
        query_plan=query_plan,
    )
    if result is not None:
        trace = result.as_trace()
        metadata["finance_numeric_trace"] = trace
        authoritative = dict(trace.get("authoritative_query_plan") or {})
        if authoritative:
            metadata["query_plan"] = authoritative
            metadata["bound_query_plan"] = authoritative
            metadata["missing_required_slot_count"] = sum(
                bool(slot.get("required_for_retrieval"))
                and str(slot.get("status") or "missing") != "filled"
                for slot in authoritative.get("evidence_slots") or []
                if isinstance(slot, dict)
            )
        _synchronize_typed_support(metadata, evidence_items, trace)


def _synchronize_typed_support(
    metadata: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    trace: dict[str, Any],
) -> None:
    verification = dict(trace.get("calculation_verification") or {})
    execution = dict(trace.get("calculation_execution") or {})
    if not verification.get("valid") or execution.get("status") != "ok":
        return
    lookup = calculation_evidence_lookup(evidence_items)
    citation_ids = [
        str(value).strip()
        for value in execution.get("citation_ids") or []
        if str(value or "").strip()
    ]
    support: list[dict[str, Any]] = []
    seen: set[int] = set()
    for evidence_id in citation_ids:
        item = lookup.get(evidence_id)
        if item is None or id(item) in seen:
            continue
        seen.add(id(item))
        support.append(item)
    metadata["typed_calculation_support_evidence"] = support
    metadata["typed_calculation_citation_ids"] = citation_ids


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
    citation_ids = [
        str(value).strip()
        for value in execution.get("citation_ids") or []
        if str(value or "").strip()
    ]
    evidence = [
        item
        for item in evidence_metadata.get("evidence") or []
        if isinstance(item, dict)
    ]
    evidence_lookup = calculation_evidence_lookup(evidence)
    if not citation_ids or any(value not in evidence_lookup for value in citation_ids):
        return "incomplete", "execution_citation_not_resolvable"
    return "good", "verified_typed_execution"
