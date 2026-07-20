from __future__ import annotations

from typing import Any

from .evidence_set_selection import select_evidence_for_plan
from .query_planning import build_query_plan, missing_slot_queries


def select_planned_evidence(
    request: Any,
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prompt = str(getattr(request, "prompt", "") or "")
    query_plan = build_query_plan(
        prompt,
        answer_type=str(
            getattr(request, "answer_type", None)
            or getattr(request, "task_type", None)
            or ""
        ),
        verification_domain=str(getattr(request, "verification_domain", None) or ""),
        planner_payload=getattr(request, "query_plan", None),
    )
    candidates = _apply_request_constraints(request, query_plan, candidates)
    selected, selection_trace, bound_plan = select_evidence_for_plan(
        prompt,
        candidates,
        query_plan,
    )
    metadata = {
        "query_plan": bound_plan.as_dict(),
        "evidence_selection_trace": selection_trace,
        "structure_metadata_coverage": selection_trace["structure_metadata_coverage"],
        "slot_coverage": selection_trace["slot_coverage"],
        "missing_required_slot_count": selection_trace["missing_required_slot_count"],
        "second_round_queries": missing_slot_queries(bound_plan),
    }
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
