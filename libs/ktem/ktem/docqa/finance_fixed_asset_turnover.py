from __future__ import annotations

import re
from typing import TypedDict

from .calculation_plan import CalculationStep
from .finance_numeric_values import (
    format_decimal,
    question_years,
    target_year,
    yearly_amounts,
)


class FixedAssetTurnoverAnswerFields(TypedDict):
    answer: str
    confidence: float
    question_type: str
    inputs: dict[str, float]
    formula: str


def is_fixed_asset_turnover(question: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(question or "").lower()).strip()
    return any(
        phrase in normalized
        for phrase in (
            "fixed asset turnover",
            "net fixed asset turnover",
            "ppe turnover",
            "pp e turnover",
            "property plant and equipment turnover",
        )
    )


def fixed_asset_turnover_inputs(
    lowered_question: str,
    text: str,
) -> tuple[float, dict[str, float]] | None:
    years = sorted(set(question_years(lowered_question)))
    target = target_year(lowered_question, years)
    previous = next((year for year in reversed(years) if year < target), "")
    revenue = yearly_amounts(
        text,
        ("net sales", "net revenue", "net revenues", "revenue"),
    )
    net_ppe = yearly_amounts(
        text,
        (
            "property, plant and equipment, net",
            "property, plant, and equipment, net",
            "net property, plant and equipment",
            "net property plant and equipment",
            "property and equipment, net",
        ),
    )
    if (
        not target
        or not previous
        or target not in revenue
        or previous not in net_ppe
        or target not in net_ppe
    ):
        return None
    average_ppe = (net_ppe[previous] + net_ppe[target]) / 2
    if average_ppe == 0:
        return None
    inputs = {
        f"net_sales_{target}": revenue[target],
        f"net_property_plant_and_equipment_{previous}": net_ppe[previous],
        f"net_property_plant_and_equipment_{target}": net_ppe[target],
    }
    return revenue[target] / average_ppe, inputs


def fixed_asset_turnover_answer_fields(
    lowered_question: str,
    text: str,
) -> FixedAssetTurnoverAnswerFields | None:
    result = fixed_asset_turnover_inputs(lowered_question, text)
    if result is None:
        return None
    value, inputs = result
    return {
        "answer": format_decimal(value),
        "confidence": 0.95,
        "question_type": "fixed_asset_turnover",
        "inputs": inputs,
        "formula": (
            "net_sales_target / average("
            "net_property_plant_and_equipment_previous, "
            "net_property_plant_and_equipment_target)"
        ),
    }


def fixed_asset_turnover_steps(
    input_ids: tuple[str, ...],
) -> tuple[tuple[CalculationStep, ...], str, str]:
    revenue_id = next(
        input_id for input_id in input_ids if input_id.startswith("net_sales_")
    )
    ppe_ids = tuple(
        input_id
        for input_id in input_ids
        if input_id.startswith("net_property_plant_and_equipment_")
    )
    return (
        (
            CalculationStep("average_net_ppe", "average", ppe_ids),
            CalculationStep(
                "result",
                "ratio",
                (revenue_id, "average_net_ppe"),
            ),
        ),
        "result",
        "ratio",
    )
