from __future__ import annotations

from typing import Any

FINANCE_ACCOUNT_ALIASES = {
    "accounts receivable": (
        "accounts receivable",
        "accounts receivables",
        "receivables",
        "trade receivables",
    ),
    "accounts payable": (
        "accounts payable",
        "accounts payables",
        "trade payables",
    ),
}


def is_cash_conversion_cycle(question: str) -> bool:
    normalized = " ".join(str(question or "").lower().split())
    return "cash conversion cycle" in normalized or " ccc " in f" {normalized} "


def is_fixed_asset_turnover(question: str) -> bool:
    normalized = " ".join(str(question or "").lower().split())
    return any(
        alias in normalized
        for alias in (
            "fixed asset turnover",
            "net fixed asset turnover",
            "pp e turnover",
            "ppe turnover",
            "property plant and equipment turnover",
        )
    )


def cash_conversion_cycle_formula(
    target_period: str,
    previous_period: str,
) -> dict[str, object] | None:
    if not target_period or not previous_period:
        return None
    operand_specs = _operand_specs(target_period, previous_period)
    inventory_previous = {"ref": f"operand:inventory:{previous_period}"}
    inventory_target = {"ref": f"operand:inventory:{target_period}"}
    receivables_previous = {"ref": f"operand:accounts_receivable:{previous_period}"}
    receivables_target = {"ref": f"operand:accounts_receivable:{target_period}"}
    payables_previous = {"ref": f"operand:accounts_payable:{previous_period}"}
    payables_target = {"ref": f"operand:accounts_payable:{target_period}"}
    cogs = {"ref": f"operand:cost_of_goods_sold:{target_period}"}
    revenue = {"ref": f"operand:net_sales:{target_period}"}
    return _formula_spec(
        operand_specs,
        _cash_conversion_cycle_expression(
            inventory_previous,
            inventory_target,
            receivables_previous,
            receivables_target,
            payables_previous,
            payables_target,
            cogs,
            revenue,
        ),
        target_period,
        previous_period,
    )


def _operand_specs(
    target_period: str,
    previous_period: str,
) -> tuple[tuple[str, str, str], ...]:
    return (
        (f"inventory:{previous_period}", "inventory", previous_period),
        (f"inventory:{target_period}", "inventory", target_period),
        (
            f"accounts_receivable:{previous_period}",
            "accounts receivable",
            previous_period,
        ),
        (
            f"accounts_receivable:{target_period}",
            "accounts receivable",
            target_period,
        ),
        (
            f"accounts_payable:{previous_period}",
            "accounts payable",
            previous_period,
        ),
        (
            f"accounts_payable:{target_period}",
            "accounts payable",
            target_period,
        ),
        (
            f"cost_of_goods_sold:{target_period}",
            "cost of goods sold",
            target_period,
        ),
        (f"net_sales:{target_period}", "net sales", target_period),
    )


def _cash_conversion_cycle_expression(*operands: dict[str, str]) -> dict[str, Any]:
    (
        inventory_previous,
        inventory_target,
        receivables_previous,
        receivables_target,
        payables_previous,
        payables_target,
        cogs,
        revenue,
    ) = operands
    days = {"constant": "365"}
    average_inventory = _average(inventory_previous, inventory_target)
    average_receivables = _average(receivables_previous, receivables_target)
    average_payables = _average(payables_previous, payables_target)
    return {
        "operator": "subtract",
        "inputs": [
            {
                "operator": "add",
                "inputs": [
                    _days_division(average_inventory, days, cogs),
                    _days_division(average_receivables, days, revenue),
                ],
            },
            _days_division(
                average_payables,
                days,
                {
                    "operator": "add",
                    "inputs": [
                        cogs,
                        {
                            "operator": "subtract",
                            "inputs": [inventory_target, inventory_previous],
                        },
                    ],
                },
            ),
        ],
    }


def _average(left: dict[str, str], right: dict[str, str]) -> dict[str, Any]:
    return {"operator": "average", "inputs": [left, right]}


def _days_division(
    numerator: dict[str, Any],
    days: dict[str, str],
    denominator: dict[str, Any],
) -> dict[str, Any]:
    return {
        "operator": "divide",
        "inputs": [
            {"operator": "multiply", "inputs": [numerator, days]},
            denominator,
        ],
    }


def _formula_spec(
    operand_specs: tuple[tuple[str, str, str], ...],
    expression: dict[str, Any],
    target_period: str,
    previous_period: str,
) -> dict[str, object]:
    return {
        "formula_id": "cash_conversion_cycle",
        "name": "cash_conversion_cycle",
        "formula_match_rule": "alias:cash_conversion_cycle",
        "formula_confidence": 1.0,
        "operand_specs": [
            {"slot_id": slot_id, "metric": metric, "period": period}
            for slot_id, metric, period in operand_specs
        ],
        "expression_ast": expression,
        "program": expression,
        "output_unit": "days",
        "target_period": target_period,
        "previous_period": previous_period,
    }
