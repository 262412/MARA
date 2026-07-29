from __future__ import annotations

from typing import Any

from .calculation_evidence_identity import calculation_evidence_lookup
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
    evidence_items = [
        item for item in getattr(bundle, "items", []) or [] if isinstance(item, dict)
    ]
    result = finance_numeric_answer(
        request_planning_question(request),
        evidence_items,
        query_plan=dict(metadata.get("query_plan") or {}),
    )
    if result is not None:
        metadata["finance_numeric_trace"] = result.as_trace()


def typed_calculation_adequacy(
    evidence_metadata: dict[str, Any],
    *,
    domain: str | None,
) -> tuple[str, str]:
    if str(domain or "").strip().lower() not in _FINANCE_DOMAINS:
        return "not_applicable", "non_finance_domain"
    query_plan = dict(evidence_metadata.get("query_plan") or {})
    constraints = dict(query_plan.get("constraints") or {})
    if constraints.get("finance_formula_status") == "unsupported":
        return "not_applicable", "unsupported_formula"
    trace = evidence_metadata.get("finance_numeric_trace")
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
