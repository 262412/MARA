from __future__ import annotations

import re
from typing import Any

from .evidence_identity import identity_of
from .evidence_selection_budget import (
    evidence_selection_budget_trace,
    evidence_stage_trace,
    selection_trace_consistency_errors,
    slot_candidate_reasons,
)
from .execution_slot_lineage import execution_slot_lineage
from .finance_query_planning import finance_metric_evidence_matches
from .query_planning import QueryPlan, slot_coverage
from .required_slot_selection import slot_requires_selection, slot_score
from .selection_score_normalization import SELECTION_SCORE_CONTRACT

_TOKEN_RE = re.compile(r"[\w.%$€£¥-]+", re.UNICODE)


def build_selection_trace(
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    bound: QueryPlan,
    budget: dict[str, int],
    context: dict[str, Any],
) -> dict[str, Any]:
    pages = _pages(selected)
    return {
        "strategy": "marginal_evidence_set_selection_v3",
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "max_items": budget["max_items"],
        "max_pages": budget["max_pages"],
        "unique_pages": len(pages),
        "selected_pages": [
            {"source_id": source, "page_label": page} for source, page in pages
        ],
        "slot_coverage": slot_coverage(bound),
        "missing_required_slot_count": sum(
            slot.required_for_retrieval and slot.status != "filled"
            for slot in bound.evidence_slots
        ),
        **context,
        **evidence_selection_budget_trace(bound, candidates, selected),
        "evidence_stage_trace": evidence_stage_trace(bound, candidates, selected),
        "trace_validation_errors": selection_trace_consistency_errors(
            bound,
            candidates,
            selected,
        ),
        "required_slot_bindings": _required_slot_bindings(
            bound,
            candidates,
            selected,
        ),
        "execution_slot_lineage": [
            execution_slot_lineage(bound, slot, candidates, selected)
            for slot in bound.evidence_slots
            if slot.required_for_execution
        ],
        "relevance_score_contract": SELECTION_SCORE_CONTRACT,
    }


def _required_slot_bindings(
    plan: QueryPlan,
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for slot in plan.evidence_slots:
        if not slot_requires_selection(slot):
            continue
        parent_available = _parent_retrieval_candidate(slot, candidates)
        output.append(
            {
                "slot_id": slot.slot_id,
                "status": slot.status,
                "retrieval_satisfied": bool(slot.evidence_ids or parent_available),
                "execution_satisfied": (
                    slot.status == "filled" if slot.required_for_execution else None
                ),
                "verification_satisfied": (
                    slot.status == "verified_support"
                    if slot.required_for_verification
                    else None
                ),
                "reason": (
                    "parent_evidence_not_materialized"
                    if slot.required_for_execution
                    and slot.status != "filled"
                    and parent_available
                    else ""
                ),
                "selected_evidence_ids": list(slot.evidence_ids),
                "best_selected_slot_score": max(
                    (
                        slot_score(plan, slot, item)
                        for item in selected
                        if identity_of(item).key in set(slot.evidence_ids)
                    ),
                    default=0.0,
                ),
                **slot_candidate_reasons(plan, slot, candidates, selected),
            }
        )
    return output


def _parent_retrieval_candidate(slot: Any, candidates: list[dict[str, Any]]) -> bool:
    metric_tokens = set(_TOKEN_RE.findall(str(slot.metric or "").lower()))
    if not metric_tokens:
        return False
    for item in candidates:
        if identity_of(item).kind in {"cell", "span"}:
            continue
        text = str(item.get("text") or "").lower()
        if metric_tokens <= set(_TOKEN_RE.findall(text)) or (
            slot.metric and finance_metric_evidence_matches(slot.metric, text)
        ):
            return True
    return False


def _pages(items: list[dict[str, Any]]) -> list[tuple[str, str]]:
    values = [
        (str(item.get("source_id") or ""), str(item.get("page_label") or ""))
        for item in items
    ]
    return list(dict.fromkeys(value for value in values if all(value)))
