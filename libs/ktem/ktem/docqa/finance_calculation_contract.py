from __future__ import annotations

from typing import Any


def finance_calculation_authoritative(query_plan: dict[str, Any]) -> bool:
    if str(query_plan.get("answer_type") or "").strip().lower() == "numeric":
        return True
    return any(
        isinstance(slot, dict)
        and bool(slot.get("required_for_execution"))
        and str(slot.get("role") or "") == "operand"
        for slot in query_plan.get("evidence_slots") or []
    )


def uses_positive_magnitude(input_id: str, question_type: str) -> bool:
    return input_id.startswith("capital_expenditure") and question_type in {
        "capital_expenditure",
        "free_cash_flow",
        "free_cash_flow_negative_capex",
        "multi_period_ratio_average",
    }
