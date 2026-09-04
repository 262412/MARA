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
        operands: tuple[str, ...] = (
            input_ids if len(input_ids) == 2 else ("prior", "current")
        )
        return (
            (CalculationStep("result", "percent_change", operands),),
            "result",
            "percent",
        )
    if question_type == "percentage_decrease":
        operands = input_ids
        return (
            (CalculationStep("result", "percent_change", operands),),
            "result",
            "percent",
        )
    if question_type in {"free_cash_flow", "free_cash_flow_negative_capex"}:
        return _free_cash_flow_steps(input_ids)
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
    if question_type == "cash_conversion_cycle":
        return _cash_conversion_cycle_steps(input_ids)
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
    input_ids: tuple[str, ...],
) -> tuple[tuple[CalculationStep, ...], str, str]:
    operating_cash_flow = next(
        (value for value in input_ids if value.startswith("operating_cash_flow")),
        "operating_cash_flow",
    )
    capital_expenditure = next(
        (value for value in input_ids if value.startswith("capital_expenditure")),
        "capital_expenditure",
    )
    return (
        (
            CalculationStep(
                "result",
                "subtract",
                (operating_cash_flow, capital_expenditure),
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


def _cash_conversion_cycle_steps(
    input_ids: tuple[str, ...],
) -> tuple[tuple[CalculationStep, ...], str, str]:
    inventory_ids = _period_pair(input_ids, "inventory_")
    receivables_ids = _period_pair(input_ids, "accounts_receivable_")
    payables_ids = _period_pair(input_ids, "accounts_payable_")
    cogs_id = next(
        input_id for input_id in input_ids if input_id.startswith("cost_of_goods_sold_")
    )
    revenue_id = next(
        input_id for input_id in input_ids if input_id.startswith("net_sales_")
    )
    inventory_previous, inventory_target = inventory_ids
    receivables_previous, receivables_target = receivables_ids
    payables_previous, payables_target = payables_ids
    return (
        (
            CalculationStep("average_inventory", "average", inventory_ids),
            CalculationStep(
                "dio_numerator",
                "multiply",
                ("average_inventory",),
                constant=Decimal("365"),
                constant_source="formula",
            ),
            CalculationStep("dio", "divide", ("dio_numerator", cogs_id)),
            CalculationStep("average_receivables", "average", receivables_ids),
            CalculationStep(
                "dso_numerator",
                "multiply",
                ("average_receivables",),
                constant=Decimal("365"),
                constant_source="formula",
            ),
            CalculationStep("dso", "divide", ("dso_numerator", revenue_id)),
            CalculationStep(
                "inventory_change",
                "subtract",
                (inventory_target, inventory_previous),
            ),
            CalculationStep("dpo_denominator", "add", (cogs_id, "inventory_change")),
            CalculationStep("average_payables", "average", payables_ids),
            CalculationStep(
                "dpo_numerator",
                "multiply",
                ("average_payables",),
                constant=Decimal("365"),
                constant_source="formula",
            ),
            CalculationStep("dpo", "divide", ("dpo_numerator", "dpo_denominator")),
            CalculationStep("operating_cycle", "add", ("dio", "dso")),
            CalculationStep("result", "subtract", ("operating_cycle", "dpo")),
        ),
        "result",
        "days",
    )


def _period_pair(input_ids: tuple[str, ...], prefix: str) -> tuple[str, str]:
    values = sorted(
        (input_id for input_id in input_ids if input_id.startswith(prefix)),
        key=lambda input_id: input_id.rsplit("_", 1)[-1],
    )
    if len(values) != 2:
        raise ValueError(f"invalid_cash_conversion_cycle_inputs:{prefix}")
    return values[0], values[1]


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
