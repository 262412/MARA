from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FormulaInputSpec:
    input_id: str
    query_slot_id: str
    metric: str
    period: str
    cardinality: int
    operator_role: str
    required_for_execution: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def formula_input_specs(
    *,
    question_type: str,
    input_ids: tuple[str, ...],
    query_plan: dict[str, Any] | None,
) -> tuple[FormulaInputSpec, ...]:
    slots = _execution_slots(query_plan)
    exact = {_slot_input_id(slot): slot for slot in slots}
    semantic_ids = _explicit_formula_input_ids(question_type, input_ids)
    output: list[FormulaInputSpec] = []
    for index, input_id in enumerate(input_ids, start=1):
        planned_input_id = semantic_ids.get(input_id, input_id)
        slot = exact.get(planned_input_id)
        if slot is None:
            slot = _collection_slot(
                planned_input_id,
                input_count=len(input_ids),
                execution_slots=slots,
            )
        cardinality = max(1, int((slot or {}).get("cardinality") or 1))
        collection = slot is not None and cardinality > 1
        output.append(
            FormulaInputSpec(
                input_id=input_id,
                query_slot_id=str((slot or {}).get("slot_id") or ""),
                metric=str((slot or {}).get("metric") or ""),
                period=str((slot or {}).get("period") or ""),
                cardinality=cardinality,
                operator_role=f"collection:{index}" if collection else input_id,
                required_for_execution=bool(
                    (slot or {}).get("required_for_execution", bool(slot))
                ),
            )
        )
    return tuple(output)


def _execution_slots(query_plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [
        dict(slot)
        for slot in (query_plan or {}).get("evidence_slots") or []
        if isinstance(slot, dict)
        and str(slot.get("slot_id") or "").startswith("operand:")
        and (
            bool(slot.get("required_for_execution"))
            or str(slot.get("role") or "") == "operand"
        )
    ]


def _slot_input_id(slot: dict[str, Any]) -> str:
    return (
        str(slot.get("slot_id") or "")
        .removeprefix("operand:")
        .replace(":", "_")
        .lower()
    )


def _collection_slot(
    input_id: str,
    *,
    input_count: int,
    execution_slots: list[dict[str, Any]],
) -> dict[str, Any] | None:
    matches = [
        slot
        for slot in execution_slots
        if int(slot.get("cardinality") or 1) == input_count
        and input_id.startswith(
            f"{str(slot.get('metric') or '').replace(' ', '_').lower()}_"
        )
    ]
    return matches[0] if len(matches) == 1 else None


def _explicit_formula_input_ids(
    question_type: str,
    input_ids: tuple[str, ...],
) -> dict[str, str]:
    mappings = {
        "working_capital": {
            "left": "current_assets",
            "right": "current_liabilities",
        },
        "current_ratio": {
            "numerator": "current_assets",
            "denominator": "current_liabilities",
        },
        "debt_to_equity": {
            "numerator": "total_debt",
            "denominator": "shareholders_equity",
        },
        "gross_margin": {
            "numerator": "gross_profit",
            "denominator": "net_sales",
        },
        "operating_margin": {
            "numerator": "operating_income",
            "denominator": "net_sales",
        },
    }
    mapping = mappings.get(question_type, {})
    return {input_id: mapping.get(input_id, input_id) for input_id in input_ids}
