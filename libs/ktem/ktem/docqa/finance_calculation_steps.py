from __future__ import annotations

import re
from decimal import Decimal

from .calculation_plan import CalculationStep
from .finance_fixed_asset_turnover import fixed_asset_turnover_steps


def calculation_steps(
    question_type: str,
    input_ids: tuple[str, ...],
) -> tuple[tuple[CalculationStep, ...], str, str]:
    if question_type == "quick_ratio":
        return _quick_ratio_steps()
    if question_type in {
        "current_ratio",
        "inventory_turnover",
        "debt_to_equity",
    }:
        return ((CalculationStep("result", "ratio", input_ids),), "result", "ratio")
    if question_type in {"operating_margin", "gross_margin"}:
        return _margin_steps(input_ids)
    if question_type == "percentage_change":
        return (
            (CalculationStep("result", "percent_change", ("prior", "current")),),
            "result",
            "percent",
        )
    if question_type in {"free_cash_flow", "free_cash_flow_negative_capex"}:
        return _free_cash_flow_steps(question_type)
    if question_type in {
        "multi_period_average",
        "multi_period_percentage_average",
    }:
        return (
            (CalculationStep("result", "average", input_ids),),
            "result",
            "percent" if question_type == "multi_period_percentage_average" else "",
        )
    if question_type == "multi_period_ratio_average":
        return _multi_period_ratio_average_steps(input_ids)
    if question_type == "inventory_turnover_average":
        return _inventory_turnover_average_steps(input_ids)
    if question_type == "fixed_asset_turnover":
        return fixed_asset_turnover_steps(input_ids)
    if question_type == "revolving_credit_capacity" and len(input_ids) > 1:
        return ((CalculationStep("result", "add", input_ids),), "result", "")
    if question_type in {"difference", "working_capital"}:
        names = (
            ("prior", "current") if question_type == "difference" else ("left", "right")
        )
        ordered = (names[1], names[0]) if question_type == "difference" else names
        return ((CalculationStep("result", "subtract", ordered),), "result", "")
    return (), input_ids[0], ""


def _quick_ratio_steps() -> tuple[tuple[CalculationStep, ...], str, str]:
    return (
        (
            CalculationStep(
                "liquid_assets",
                "subtract",
                ("current_assets", "inventories"),
            ),
            CalculationStep(
                "result",
                "ratio",
                ("liquid_assets", "current_liabilities"),
            ),
        ),
        "result",
        "ratio",
    )


def _margin_steps(
    input_ids: tuple[str, ...],
) -> tuple[tuple[CalculationStep, ...], str, str]:
    return (
        (
            CalculationStep("ratio", "ratio", input_ids),
            CalculationStep(
                "result",
                "multiply",
                ("ratio",),
                constant=Decimal("100"),
            ),
        ),
        "result",
        "percent",
    )


def _free_cash_flow_steps(
    question_type: str,
) -> tuple[tuple[CalculationStep, ...], str, str]:
    operator = "add" if question_type == "free_cash_flow_negative_capex" else "subtract"
    return (
        (
            CalculationStep(
                "result",
                operator,
                ("operating_cash_flow", "capital_expenditure"),
            ),
        ),
        "result",
        "",
    )


def _inventory_turnover_average_steps(
    input_ids: tuple[str, ...],
) -> tuple[tuple[CalculationStep, ...], str, str]:
    inventory_ids = tuple(
        input_id for input_id in input_ids if input_id.startswith("inventory_")
    )
    return (
        (
            CalculationStep("average_inventory", "average", inventory_ids),
            CalculationStep(
                "result",
                "ratio",
                ("cost_of_goods_sold", "average_inventory"),
            ),
        ),
        "result",
        "ratio",
    )


def _multi_period_ratio_average_steps(
    input_ids: tuple[str, ...],
) -> tuple[tuple[CalculationStep, ...], str, str]:
    years = list(
        dict.fromkeys(
            match.group(0)
            for input_id in input_ids
            if (match := re.search(r"(?:19|20)\d{2}", input_id))
        )
    )
    steps: list[CalculationStep] = []
    percentage_ids: list[str] = []
    for year in years:
        period_inputs = [input_id for input_id in input_ids if input_id.endswith(year)]
        if len(period_inputs) != 2:
            raise ValueError(f"invalid_multi_period_ratio_inputs:{year}")
        numerator, denominator = period_inputs
        ratio_id = f"ratio_{year}"
        percentage_id = f"percentage_{year}"
        steps.extend(
            (
                CalculationStep(ratio_id, "ratio", (numerator, denominator)),
                CalculationStep(
                    percentage_id,
                    "multiply",
                    (ratio_id,),
                    constant=Decimal("100"),
                ),
            )
        )
        percentage_ids.append(percentage_id)
    steps.append(CalculationStep("result", "average", tuple(percentage_ids)))
    return tuple(steps), "result", "percent"
