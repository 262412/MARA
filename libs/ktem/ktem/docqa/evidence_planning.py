from __future__ import annotations

from typing import Any

from .evidence_set_selection import select_evidence_for_plan
from .query_planning import (
    ensure_request_query_plan,
    missing_slot_queries,
    missing_slot_requests,
    request_planning_question,
)
from .selection_assessment_snapshot import SelectionAssessmentSnapshot


def select_planned_evidence(
    request: Any,
    candidates: list[dict[str, Any]],
    *,
    assessments: SelectionAssessmentSnapshot | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prompt = request_planning_question(request)
    query_plan = ensure_request_query_plan(request)
    candidates = _apply_request_constraints(request, query_plan, candidates)
    selected, selection_trace, bound_plan = select_evidence_for_plan(
        prompt,
        candidates,
        query_plan,
        assessments=assessments,
    )
    planned_plan = getattr(request, "planned_query_plan", None) or query_plan
    bound_state_version = int(getattr(request, "query_plan_state_version", 0) or 0) + 1
    request.query_plan = bound_plan
    request.query_plan_id = bound_plan.plan_id
    request.query_plan_state_version = bound_state_version
    planned_query_plan = planned_plan.as_dict()
    planned_query_plan.update({"stage": "planned", "state_version": 0})
    bound_query_plan = bound_plan.as_dict()
    bound_query_plan.update({"stage": "bound", "state_version": bound_state_version})
    metadata = {
        "query_plan": bound_plan.as_dict(),
        "query_plan_id": bound_plan.plan_id,
        "planned_query_plan": planned_query_plan,
        "bound_query_plan": bound_query_plan,
        "evidence_selection_trace": selection_trace,
        "structure_metadata_coverage": selection_trace["structure_metadata_coverage"],
        "slot_coverage": selection_trace["slot_coverage"],
        "missing_required_slot_count": selection_trace["missing_required_slot_count"],
        "second_round_queries": missing_slot_queries(bound_plan),
        "second_round_requests": missing_slot_requests(bound_plan),
    }
    if assessments is not None:
        assessment_audit = assessments.audit()
        if assessment_audit["slots"]:
            metadata["boolean_assessment_cache"] = assessment_audit
    return selected, metadata


def _apply_request_constraints(
    request: Any,
    query_plan: Any,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    constrained = list(candidates)
    active_file_id = str(getattr(request, "active_file_id", "") or "").strip()
    if active_file_id:
        source_matches = [
            item
            for item in constrained
            if str(item.get("source_id") or "") == active_file_id
        ]
        if source_matches:
            constrained = source_matches
    page_number = getattr(request, "page_number", None)
    page_scoped = str(getattr(request, "qa_scope", "") or "").lower() == "page"
    multi_page = query_plan.question_type in {
        "cross_page",
        "multi_period_numeric",
        "numeric",
    }
    if page_number is None or (multi_page and not page_scoped):
        return constrained
    page_matches = [
        item
        for item in constrained
        if str(item.get("page_label") or "") == str(page_number)
    ]
    return page_matches or constrained
