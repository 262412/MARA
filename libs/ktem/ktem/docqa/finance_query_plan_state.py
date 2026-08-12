from __future__ import annotations

from typing import Any

from .query_plan_schema import slot_binding_state


def operand_slot_state(
    operands: list[dict[str, Any]],
    slot: dict[str, Any],
) -> dict[str, Any]:
    evidence_ids = list(
        dict.fromkeys(
            str(operand.get("evidence_identity") or operand.get("evidence_id") or "")
            for operand in operands
            if str(operand.get("evidence_identity") or operand.get("evidence_id") or "")
        )
    )
    state_slot = {**slot, "status": "filled", "evidence_ids": evidence_ids}
    state_items = [
        {
            "canonical_id": str(
                operand.get("evidence_identity") or operand.get("evidence_id") or ""
            ).strip(),
            "facility_identity": str(operand.get("facility_identity") or "").strip(),
            "value": operand.get("value"),
        }
        for operand in operands
        if str(operand.get("evidence_identity") or operand.get("evidence_id") or "")
    ]
    state = {
        "role": "operand",
        "required_for_execution": True,
        "status": (
            slot_binding_state(
                state_slot,
                state_items,
                materialized=lambda item: item.get("value") not in (None, ""),
            )
            if evidence_ids
            else "missing"
        ),
        "evidence_ids": evidence_ids,
    }
    for field_name in (
        "source_id",
        "unit",
        "scale",
        "currency",
        "period",
        "period_kind",
        "statement_kind",
        "financial_scope",
        "table_instance_id",
        "table_group_id",
        "dimension_binding_scope",
    ):
        values = list(
            dict.fromkeys(
                str(operand.get(field_name) or "")
                for operand in operands
                if str(operand.get(field_name) or "")
            )
        )
        if values:
            state[field_name] = values[-1]
    return state
