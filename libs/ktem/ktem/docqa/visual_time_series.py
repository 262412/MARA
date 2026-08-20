from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .evidence_identity import identity_of
from .query_evidence_binding_support import score_evidence_for_slot
from .query_plan_schema import QueryPlan

VISUAL_TIME_SERIES_ANSWER_REVISION_CONTRACT = "visual_time_series_answer_revision.v1"


def revise_visual_time_series_answer(
    request: Any,
    bundle: Any,
    answer: str,
) -> tuple[str, dict[str, Any] | None]:
    authority = visual_time_series_authority(request, bundle)
    if authority is None:
        return answer, None
    revised = str(authority["answer"])
    if _normalized_answer(answer) == _normalized_answer(revised):
        return answer, None
    trace = {
        "stage": "answer_revision",
        "contract_id": VISUAL_TIME_SERIES_ANSWER_REVISION_CONTRACT,
        "original_candidate": str(answer or ""),
        "revised_candidate": revised,
        "authority_evidence_ids": list(authority["evidence_ids"]),
        "authority_changed": True,
        "revision_reason": "complete_typed_visual_time_series",
        "stop_reason": "visual_time_series_revision_pending_verification",
    }
    metadata = getattr(bundle, "metadata", None)
    if isinstance(metadata, dict):
        metadata["visual_time_series_answer_revision"] = dict(trace)
    return revised, trace


def validated_visual_time_series_authority(
    request: Any,
    bundle: Any,
    answer: str,
) -> dict[str, Any] | None:
    authority = visual_time_series_authority(request, bundle)
    if authority is None or _normalized_answer(
        authority["answer"]
    ) != _normalized_answer(answer):
        return None
    return authority


def visual_time_series_authority(
    request: Any,
    bundle: Any,
) -> dict[str, Any] | None:
    plan = getattr(request, "query_plan", None)
    if not isinstance(plan, QueryPlan):
        return None
    slots = [
        slot
        for slot in plan.evidence_slots
        if slot.required_for_verification
        and slot.statement_kind == "visual_time_series_cell"
    ]
    if len(slots) < 2 or len({slot.period for slot in slots}) != len(slots):
        return None
    items = [
        item for item in getattr(bundle, "items", []) or [] if isinstance(item, dict)
    ]
    by_identity = _unique_items_by_identity(items)
    if by_identity is None:
        return None
    rows: list[tuple[Any, dict[str, Any], Decimal]] = []
    bindings: dict[str, list[str]] = {}
    for slot in slots:
        if str(slot.status or "") not in {"filled", "verified_support"}:
            return None
        evidence_ids = list(dict.fromkeys(slot.evidence_ids))
        if len(evidence_ids) != 1:
            return None
        item = by_identity.get(evidence_ids[0])
        if (
            item is None
            or score_evidence_for_slot(
                slot,
                item,
                requires_structure=True,
            )
            <= 0
        ):
            return None
        try:
            numeric_value = Decimal(str(item.get("value")).replace(",", ""))
        except (InvalidOperation, TypeError):
            return None
        bindings[slot.slot_id] = evidence_ids
        rows.append((slot, item, numeric_value))
    if not _coherent_series(rows):
        return None
    answer = _canonical_answer(rows)
    evidence_ids = [
        evidence_id for slot in slots for evidence_id in bindings[slot.slot_id]
    ]
    required_slot_ids = [slot.slot_id for slot in slots]
    return {
        "answer": answer,
        "evidence_ids": evidence_ids,
        "typed_visual_path": {
            "contract_id": "typed_visual_evidence_path.v1",
            "required_slot_ids": required_slot_ids,
            "verified_support_slot_ids": required_slot_ids,
            "slot_bindings": bindings,
            "query_plan_state_version": int(
                getattr(request, "query_plan_state_version", 0) or 0
            ),
        },
    }


def _coherent_series(rows: list[tuple[Any, dict[str, Any], Decimal]]) -> bool:
    keys = {
        (
            str(item.get("source_id") or item.get("file_id") or "").strip(),
            str(item.get("page_label") or "").strip(),
            str(item.get("table_id") or item.get("table_instance_id") or "").strip(),
            _normalized_metric(item.get("row_label")),
        )
        for _slot, item, _value in rows
    }
    return len(keys) == 1 and all(next(iter(keys)))


def _unique_items_by_identity(
    items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]] | None:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        try:
            identity = identity_of(item).key
        except (TypeError, ValueError):
            continue
        existing = indexed.get(identity)
        if existing is not None and existing != item:
            return None
        indexed[identity] = item
    return indexed


def _canonical_answer(rows: list[tuple[Any, dict[str, Any], Decimal]]) -> str:
    ordered = sorted(rows, key=lambda row: _period_sort_key(str(row[0].period)))
    metric = _display_metric(ordered[0][1].get("row_label"))
    observations = [
        f"{_display_value(item.get('value'))} in {slot.period}"
        for slot, item, _value in ordered
    ]
    series_text = _joined_observations(observations)
    values = [value for _slot, _item, value in ordered]
    periods = [str(slot.period) for slot, _item, _value in ordered]
    peak_index = max(range(len(values)), key=values.__getitem__)
    low_index = min(range(len(values)), key=values.__getitem__)
    if peak_index < low_index < len(values) - 1 and values[-1] > values[-2]:
        trend = (
            f"It peaked in {periods[peak_index]}, declined to its low in "
            f"{periods[low_index]}, then increased in {periods[-1]}."
        )
    elif low_index < peak_index < len(values) - 1 and values[-1] < values[-2]:
        trend = (
            f"It reached its low in {periods[low_index]}, rose to its peak in "
            f"{periods[peak_index]}, then decreased in {periods[-1]}."
        )
    else:
        if values[-1] > values[0]:
            direction = "higher"
        elif values[-1] < values[0]:
            direction = "lower"
        else:
            direction = "unchanged"
        trend = (
            f"Its peak was in {periods[peak_index]} and its low was in "
            f"{periods[low_index]}, ending {direction} than in {periods[0]}."
        )
    return f"{metric} was {series_text}. {trend}"


def _joined_observations(values: list[str]) -> str:
    if len(values) == 2:
        return " and ".join(values)
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _display_metric(value: Any) -> str:
    text = re.sub(r"\*+\d*\s*$", "", str(value or "").strip())
    return text or "The requested metric"


def _normalized_metric(value: Any) -> str:
    return " ".join(_display_metric(value).casefold().split())


def _display_value(value: Any) -> str:
    return str(value or "").strip().replace(",", "")


def _period_sort_key(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (10**9, value)


def _normalized_answer(value: Any) -> str:
    return " ".join(str(value or "").strip().split())
