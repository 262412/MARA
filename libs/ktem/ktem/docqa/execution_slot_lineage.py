from __future__ import annotations

from typing import Any

from .evidence_identity import evidence_aliases, identity_of
from .finance_scale import source_scale_evidence
from .query_planning import QueryPlan
from .required_slot_selection import slot_score
from .selection_assessment_table import SelectionAssessmentTable


def execution_slot_lineage(
    plan: QueryPlan,
    slot: Any,
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    *,
    assessments: SelectionAssessmentTable | None = None,
) -> dict[str, Any]:
    matching = [
        item
        for item in candidates
        if slot_score(plan, slot, item, assessments=assessments) > 0
    ]
    parents = [item for item in matching if not is_atomic_operand_candidate(item)]
    cells = [item for item in matching if is_atomic_operand_candidate(item)]
    selected_lookup = {_identity(item): item for item in selected}
    selected_items = [
        selected_lookup[identity]
        for identity in slot.evidence_ids
        if identity in selected_lookup
    ]
    selected_cell = next(
        (item for item in selected_items if is_atomic_operand_candidate(item)),
        None,
    )
    selected_parent = linked_parent_candidate(selected_cell, parents)
    rejection_reasons: list[str] = []
    if slot.role == "operand" and not cells:
        rejection_reasons.append("no_executable_atomic_cell")
    elif slot.role == "operand" and selected_cell is None:
        rejection_reasons.append("atomic_cell_not_selected")
    return {
        "slot_id": slot.slot_id,
        "slot_query": slot.query,
        "parent_candidates": [_identity(item) for item in parents],
        "selected_parent": _identity(selected_parent) if selected_parent else "",
        "materialized_cell_candidates": [
            _identity(item)
            for item in cells
            if str(item.get("materialization_source_id") or "")
        ],
        "reranker_observations": (
            list(
                dict(selected_cell.get("metadata") or {}).get("reranker_observations")
                or []
            )
            if selected_cell
            else []
        ),
        "selected_cell": _identity(selected_cell) if selected_cell else "",
        "binding_score": slot_score(
            plan,
            slot,
            selected_cell,
            assessments=assessments,
        )
        if selected_cell
        else 0.0,
        "rejection_reasons": rejection_reasons,
        "execution_operand": dict(selected_cell) if selected_cell else {},
    }


def linked_parent_candidate(
    cell: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if cell is None:
        return None
    direct_ids = {
        str(cell.get(field) or "").strip()
        for field in ("materialization_source_id", "parent_element_id")
        if str(cell.get(field) or "").strip()
    }
    table_ids = {
        str(cell.get(field) or "").strip()
        for field in ("table_id", "table_instance_id", "table_group_id")
        if str(cell.get(field) or "").strip()
    }
    cell_page = _page(cell)
    for candidate in candidates:
        if is_atomic_operand_candidate(candidate):
            continue
        if direct_ids & evidence_aliases(candidate):
            return candidate
        candidate_tables = {
            str(candidate.get(field) or "").strip()
            for field in ("table_id", "table_instance_id", "table_group_id")
            if str(candidate.get(field) or "").strip()
        }
        if table_ids & candidate_tables and (
            not all(cell_page) or _page(candidate) == cell_page
        ):
            return candidate
    return None


def linked_dimension_candidate(
    cell: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if cell is None:
        return None
    _scale, evidence_id = source_scale_evidence(cell, candidates)
    if not evidence_id:
        return None
    return next(
        (
            candidate
            for candidate in candidates
            if evidence_id in evidence_aliases(candidate)
        ),
        None,
    )


def is_atomic_operand_candidate(item: dict[str, Any]) -> bool:
    return identity_of(item).kind in {"cell", "span"} and item.get("value") not in (
        None,
        "",
    )


def _identity(item: dict[str, Any]) -> str:
    return identity_of(item).key


def _page(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("source_id") or ""),
        str(item.get("page_label") or ""),
    )
