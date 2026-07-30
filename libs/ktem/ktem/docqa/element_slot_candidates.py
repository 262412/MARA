from __future__ import annotations

from dataclasses import replace
from typing import Any

from .evidence_identity import identity_of
from .finance_query_planning import finance_metric_evidence_matches
from .financial_statement_identity import matches_required_financial_identity
from .query_planning import score_evidence_for_slot
from .required_slot_selection import required_slot_shortlist

EXECUTION_PARENT_CANDIDATE_QUOTA = 2


def element_records_for_pipeline(pipeline: Any) -> list[dict[str, Any]]:
    records = getattr(pipeline, "element_index_records", None)
    if not records:
        return []
    return [dict(item) for item in records if isinstance(item, dict)]


def element_modality_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        modality = str(
            record.get("modality") or record.get("element_type") or "element"
        ).strip()
        counts[modality or "element"] = counts.get(modality or "element", 0) + 1
    return counts


def shortlist_element_candidates(
    ranked: list[dict[str, Any]],
    plan: Any,
    *,
    active_slot_id: str,
    candidate_limit: int,
) -> tuple[list[dict[str, Any]], int, int, int]:
    shortlist_plan = _active_slot_plan(plan, active_slot_id)
    selected, restored_required = required_slot_shortlist(
        ranked,
        shortlist_plan,
        candidate_limit=candidate_limit,
    )
    parent_candidates = _execution_parent_candidates(ranked, shortlist_plan)
    if parent_candidates:
        selected = _reserve_candidates(
            parent_candidates,
            selected,
            candidate_limit=candidate_limit,
        )
        original_index = {
            identity_of(item).key: index for index, item in enumerate(ranked)
        }
        restored_required += sum(
            original_index[identity_of(item).key] >= candidate_limit
            for item in parent_candidates
            if item in selected
        )
    return (
        selected,
        restored_required,
        _active_slot_candidate_count(selected, shortlist_plan),
        sum(item in selected for item in parent_candidates),
    )


def _active_slot_plan(plan: Any, slot_id: str) -> Any:
    if not slot_id:
        return plan
    slots = tuple(slot for slot in plan.evidence_slots if slot.slot_id == slot_id)
    if not slots:
        return plan
    return replace(
        plan,
        evidence_slots=slots,
        subqueries=tuple(slot.query for slot in slots if slot.query),
    )


def _active_slot_candidate_count(items: list[dict[str, Any]], plan: Any) -> int:
    if len(plan.evidence_slots) != 1:
        return 0
    slot = plan.evidence_slots[0]
    return sum(_slot_or_parent_score(plan, slot, item) > 0 for item in items)


def _execution_parent_candidates(
    ranked: list[dict[str, Any]],
    plan: Any,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for slot in plan.evidence_slots:
        if not (slot.required_for_execution and slot.role == "operand"):
            continue
        parents = sorted(
            (
                (_execution_parent_score(slot, item), index, item)
                for index, item in enumerate(ranked)
                if _execution_parent_score(slot, item) > 0
            ),
            key=lambda row: (-row[0], row[1]),
        )
        for _score, _index, parent in parents[:EXECUTION_PARENT_CANDIDATE_QUOTA]:
            identity = identity_of(parent).key
            if identity in selected_ids:
                continue
            selected_ids.add(identity)
            candidates.append(parent)
    return candidates


def _reserve_candidates(
    reserved: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    *,
    candidate_limit: int,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for item in [*reserved, *selected]:
        identity = identity_of(item).key
        if identity in selected_ids:
            continue
        selected_ids.add(identity)
        output.append(item)
        if len(output) >= candidate_limit:
            break
    return output


def _slot_or_parent_score(plan: Any, slot: Any, item: dict[str, Any]) -> float:
    score = score_evidence_for_slot(
        slot,
        item,
        requires_structure=bool(plan.constraints.get("requires_structure")),
    )
    return max(score, _execution_parent_score(slot, item))


def _execution_parent_score(slot: Any, item: dict[str, Any]) -> float:
    if not (slot.required_for_execution and slot.role == "operand"):
        return 0.0
    if str(item.get("evidence_level") or "").strip().lower() == "cell":
        return 0.0
    modality = str(item.get("modality") or item.get("element_type") or "").lower()
    if not (
        item.get("table_id") or item.get("table_instance_id") or modality == "table"
    ):
        return 0.0
    text = " ".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "caption", "table_title")
    ).lower()
    if not text.strip() or (slot.period and str(slot.period).lower() not in text):
        return 0.0
    if slot.metric and not finance_metric_evidence_matches(slot.metric, text):
        return 0.0
    if not matches_required_financial_identity(
        item,
        slot.statement_kind,
        slot.financial_scope,
    ):
        return 0.0
    return 1.0 + _formal_statement_heading_score(slot.statement_kind, text)


def _formal_statement_heading_score(statement_kind: str, text: str) -> float:
    phrases = {
        "balance_sheet": (
            "balance sheet",
            "statement of financial position",
        ),
        "cash_flow_statement": (
            "statement of cash flows",
            "statement of cash flow",
        ),
        "income_statement": (
            "statement of income",
            "statement of operations",
            "income statement",
        ),
    }
    return float(any(phrase in text for phrase in phrases.get(statement_kind, ())))
