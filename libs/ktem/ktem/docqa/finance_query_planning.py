from __future__ import annotations

import re

FinanceOperandSpecs = tuple[tuple[str, str, str], ...]

FINANCE_METRIC_ALIASES = {
    "adjusted ebitda": (
        "adjusted ebitda",
        "adjusted non gaap ebitda",
        "adjusted non-gaap ebitda",
        "adj ebitda",
    ),
    "capital expenditure": (
        "capital expenditure",
        "capital expenditures",
        "capital spending",
        "capex",
        "purchases of land buildings and equipment",
        "purchase of property plant and equipment",
        "purchases of property plant and equipment",
        "purchases of property, plant and equipment",
        "purchases of property, plant and equipment (pp&e)",
    ),
    "cash and cash equivalents": (
        "cash and cash equivalents",
        "cash & cash equivalents",
    ),
    "cost of goods sold": (
        "cost of goods sold",
        "cost of products sold",
        "cost of revenues",
        "cost of sales",
        "cogs",
    ),
    "total current assets": ("total current assets",),
    "current assets": ("current assets", "total current assets"),
    "current liabilities": ("current liabilities", "total current liabilities"),
    "gross profit": ("gross profit",),
    "inventory": ("inventory", "inventories"),
    "net sales": (
        "net sales",
        "net revenue",
        "net revenues",
        "revenue",
        "revenues",
    ),
    "revenue": (
        "net sales",
        "net revenue",
        "net revenues",
        "revenue",
        "revenues",
    ),
    "operating cash flow": (
        "operating cash flow",
        "cash from operations",
        "net cash provided by operating activities",
    ),
    "operating income": ("operating income", "operating profit"),
    "net property plant and equipment": (
        "net property plant and equipment",
        "net property, plant and equipment",
        "net property, plant, and equipment",
        "property, plant and equipment, net",
        "property, plant, and equipment, net",
        "property and equipment, net",
    ),
    "property plant and equipment": (
        "property plant and equipment",
        "property, plant and equipment",
        "property, plant, and equipment",
        "property and equipment",
    ),
    "revolving credit capacity": (
        "revolving credit agreement",
        "revolving credit agreements",
        "credit facility",
        "credit facilities",
        "may borrow",
    ),
    "shareholders equity": (
        "shareholders equity",
        "shareholders' equity",
        "stockholders equity",
        "stockholders' equity",
    ),
    "total assets": ("total assets",),
    "total debt": ("total debt", "long term debt", "short term debt"),
}


def finance_metric_phrase_matches(metric: str, text: str) -> bool:
    normalized_text = f" {_normalized_metric_phrase(text)} "
    return any(
        f" {_normalized_metric_phrase(alias)} " in normalized_text
        for alias in FINANCE_METRIC_ALIASES.get(metric, (metric,))
        if _normalized_metric_phrase(alias)
    )


def finance_metric_evidence_matches(metric: str, text: str) -> bool:
    if not finance_metric_phrase_matches(metric, text):
        return False
    if metric != "inventory":
        return True
    normalized = _normalized_metric_phrase(text)
    cash_flow_statement = (
        "statement of cash flows" in normalized
        or "statements of cash flows" in normalized
    )
    inventory_change = (
        "changes in current assets and liabilities" in normalized
        or "changes in operating assets and liabilities" in normalized
    )
    return not (cash_flow_statement and inventory_change)


def finance_revenue_row_quality(metric: str, row_label: str) -> int:
    if metric not in {"net sales", "revenue"}:
        return 0
    normalized = _normalized_metric_phrase(row_label)
    if normalized == "net sales":
        return 4
    if normalized in {
        "net revenue",
        "net revenues",
        "total net revenue",
        "total net revenues",
        "total revenue",
        "total revenues",
    }:
        return 3
    if normalized in {"revenue", "revenues"}:
        return 2
    return 0


def _normalized_metric_phrase(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def finance_operand_specs(
    question: str,
    periods: list[str],
) -> FinanceOperandSpecs:
    lowered = str(question or "").lower()
    formula = finance_formula_spec(lowered, periods)
    if formula is not None:
        operand_specs = formula.get("operand_specs")
        if not isinstance(operand_specs, list):
            return ()
        return tuple(
            (
                str(spec["slot_id"]),
                str(spec["metric"]),
                str(spec["period"]),
            )
            for spec in operand_specs
            if isinstance(spec, dict)
        )
    if finance_formula_status(lowered, periods) == "unsupported":
        return ()
    current_period = finance_target_period(lowered, periods)
    named_specs = _named_formula_specs(lowered, periods, current_period)
    if named_specs:
        return named_specs

    metrics = finance_metrics_in_question(lowered)
    if "ratio" in lowered and len(metrics) >= 2:
        return same_period_specs(
            current_period,
            *((metric.replace(" ", "_"), metric) for metric in metrics[:2]),
        )
    if len(periods) >= 2 and metrics:
        metric = metrics[0]
        return tuple(
            (f"{metric.replace(' ', '_')}:{period}", metric, period)
            for period in periods
        )
    if not metrics:
        return ()
    metric = metrics[0]
    slot_id = metric.replace(" ", "_")
    if current_period:
        slot_id = f"{slot_id}:{current_period}"
    return ((slot_id, metric, current_period),)


def finance_formula_spec(
    question: str,
    periods: list[str],
) -> dict[str, object] | None:
    lowered = str(question or "").lower()
    if _is_fixed_asset_turnover(lowered):
        return _fixed_asset_turnover_formula(lowered, periods)
    if "inventory turnover" in lowered:
        return _inventory_turnover_formula(lowered, periods)
    ratio_specs = _multi_period_ratio_specs(lowered, periods)
    if ratio_specs and "average" in lowered:
        return _multi_period_percentage_formula(lowered, ratio_specs)
    return None


def _inventory_turnover_formula(
    question: str,
    periods: list[str],
) -> dict[str, object] | None:
    target_period = finance_target_period(question, periods)
    operand_specs = _inventory_turnover_specs(periods, target_period)
    inventory_specs = [spec for spec in operand_specs if spec[1] == "inventory"]
    if not target_period or len(inventory_specs) < 2:
        return None
    inventory_refs = [
        {"ref": f"operand:{slot_id}"} for slot_id, _metric, _period in inventory_specs
    ]
    return _formula_spec(
        formula_id="inventory_turnover_average",
        match_rule="alias:inventory_turnover_average_inventory",
        operand_specs=operand_specs,
        expression={
            "operator": "divide",
            "inputs": [
                {"ref": "operand:cost_of_goods_sold"},
                {"operator": "average", "inputs": inventory_refs},
            ],
        },
        answer_unit="ratio",
        target_period=target_period,
        previous_period=inventory_specs[0][2],
    )


def _fixed_asset_turnover_formula(
    question: str,
    periods: list[str],
) -> dict[str, object] | None:
    target_period = finance_target_period(question, periods)
    previous_period = _previous_period(periods, target_period)
    if not target_period or not previous_period:
        return None
    revenue = f"operand:net_sales:{target_period}"
    previous_ppe = f"operand:net_property_plant_and_equipment:{previous_period}"
    target_ppe = f"operand:net_property_plant_and_equipment:{target_period}"
    return _formula_spec(
        formula_id="fixed_asset_turnover",
        match_rule="alias:fixed_asset_turnover",
        operand_specs=(
            (f"net_sales:{target_period}", "net sales", target_period),
            (
                f"net_property_plant_and_equipment:{previous_period}",
                "net property plant and equipment",
                previous_period,
            ),
            (
                f"net_property_plant_and_equipment:{target_period}",
                "net property plant and equipment",
                target_period,
            ),
        ),
        expression={
            "operator": "divide",
            "inputs": [
                {"ref": revenue},
                {
                    "operator": "average",
                    "inputs": [{"ref": previous_ppe}, {"ref": target_ppe}],
                },
            ],
        },
        answer_unit="ratio",
        target_period=target_period,
        previous_period=previous_period,
    )


def _multi_period_percentage_formula(
    question: str,
    ratio_specs: FinanceOperandSpecs,
) -> dict[str, object]:
    years = list(dict.fromkeys(period for _slot, _metric, period in ratio_specs))
    numerator, denominator = finance_metrics_in_question(question)[:2]
    numerator = "net sales" if numerator == "revenue" else numerator
    denominator = "net sales" if denominator == "revenue" else denominator
    percentages = [
        {
            "operator": "multiply",
            "inputs": [
                {
                    "operator": "divide",
                    "inputs": [
                        {"ref": f"operand:{numerator.replace(' ', '_')}:{period}"},
                        {"ref": f"operand:{denominator.replace(' ', '_')}:{period}"},
                    ],
                },
                {"constant": "100"},
            ],
        }
        for period in years
    ]
    return _formula_spec(
        formula_id="multi_period_percentage_of_average",
        match_rule="pattern:average_metric_as_percentage_of_metric",
        operand_specs=ratio_specs,
        expression={"operator": "average", "inputs": percentages},
        answer_unit="percent",
        target_period=years[-1],
        previous_period=years[-2] if len(years) > 1 else "",
    )


def finance_formula_status(question: str, periods: list[str]) -> str:
    if finance_formula_spec(question, periods) is not None:
        return "supported"
    lowered = str(question or "").lower()
    unsupported_turnover = "turnover" in lowered and not (
        _is_fixed_asset_turnover(lowered) or "inventory turnover" in lowered
    )
    unsupported_percentage_of = bool(
        re.search(r"\bas\s+(?:a\s+)?(?:%|percent(?:age)?)\s+of\b", lowered)
    )
    if unsupported_turnover or unsupported_percentage_of:
        return "unsupported"
    return "not_applicable"


def _formula_spec(
    *,
    formula_id: str,
    match_rule: str,
    operand_specs: FinanceOperandSpecs,
    expression: dict[str, object],
    answer_unit: str,
    target_period: str,
    previous_period: str,
) -> dict[str, object]:
    serialized_operands = [
        {"slot_id": slot_id, "metric": metric, "period": period}
        for slot_id, metric, period in operand_specs
    ]
    return {
        "formula_id": formula_id,
        "name": formula_id,
        "formula_match_rule": match_rule,
        "formula_confidence": 1.0,
        "operand_specs": serialized_operands,
        "expression_ast": expression,
        "program": expression,
        "output_unit": answer_unit,
        "target_period": target_period,
        "previous_period": previous_period,
    }


def finance_fact_specs(
    question: str,
    periods: list[str],
) -> FinanceOperandSpecs:
    lowered = str(question or "").lower()
    metrics = finance_metrics_in_question(lowered)
    if not metrics and "segment" in lowered and re.search(r"\bsales?\b", lowered):
        metrics = ["net sales"]
    if not metrics:
        return ()
    metric = metrics[0]
    target_periods = periods or [finance_target_period(lowered, periods)]
    return tuple(
        (
            f"{metric.replace(' ', '_')}:{period}" if period else metric,
            metric,
            period,
        )
        for period in target_periods
    )


def _named_formula_specs(
    question: str,
    periods: list[str],
    current_period: str,
) -> FinanceOperandSpecs:
    if _is_fixed_asset_turnover(question):
        previous_period = _previous_period(periods, current_period)
        if previous_period and current_period:
            return (
                (f"net_sales:{current_period}", "net sales", current_period),
                (
                    f"net_property_plant_and_equipment:{previous_period}",
                    "net property plant and equipment",
                    previous_period,
                ),
                (
                    f"net_property_plant_and_equipment:{current_period}",
                    "net property plant and equipment",
                    current_period,
                ),
            )
    multi_period_ratio = _multi_period_ratio_specs(question, periods)
    if multi_period_ratio:
        return multi_period_ratio
    if "quick ratio" in question:
        return same_period_specs(
            current_period,
            ("current_assets", "current assets"),
            ("inventory", "inventory"),
            ("current_liabilities", "current liabilities"),
        )
    if "current ratio" in question or "working capital" in question:
        return same_period_specs(
            current_period,
            ("current_assets", "current assets"),
            ("current_liabilities", "current liabilities"),
        )
    if "free cash flow" in question or re.search(r"\bfcf\b", question):
        return same_period_specs(
            current_period,
            ("operating_cash_flow", "operating cash flow"),
            ("capital_expenditure", "capital expenditure"),
        )
    if "inventory turnover" in question:
        return _inventory_turnover_specs(periods, current_period)
    if "operating margin" in question:
        return same_period_specs(
            current_period,
            ("operating_income", "operating income"),
            ("net_sales", "net sales"),
        )
    if "gross margin" in question:
        return same_period_specs(
            current_period,
            ("gross_profit", "gross profit"),
            ("net_sales", "net sales"),
        )
    if "debt" in question and "equity" in question:
        return same_period_specs(
            current_period,
            ("total_debt", "total debt"),
            ("shareholders_equity", "shareholders equity"),
        )
    return ()


def _is_fixed_asset_turnover(question: str) -> bool:
    normalized = _normalized_metric_phrase(question)
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


def _previous_period(periods: list[str], target_period: str) -> str:
    ordered = sorted(
        {
            value
            for value in periods
            if re.fullmatch(r"(?:19|20)\d{2}", str(value or ""))
        }
    )
    earlier = [value for value in ordered if value < target_period]
    return earlier[-1] if earlier else ""


def _multi_period_ratio_specs(
    question: str,
    periods: list[str],
) -> FinanceOperandSpecs:
    percentage_of = bool(
        re.search(r"\bas\s+(?:a\s+)?(?:%|percent(?:age)?)\s+of\b", question)
    )
    metrics = finance_metrics_in_question(question)
    if not percentage_of or len(periods) < 2 or len(metrics) < 2:
        return ()
    numerator, denominator = metrics[:2]
    numerator = "net sales" if numerator == "revenue" else numerator
    denominator = "net sales" if denominator == "revenue" else denominator
    return tuple(
        (
            f"{metric.replace(' ', '_')}:{period}",
            metric,
            period,
        )
        for period in periods
        for metric in (numerator, denominator)
    )


def _inventory_turnover_specs(
    periods: list[str],
    current_period: str,
) -> FinanceOperandSpecs:
    inventory_periods = sorted(set(periods))
    if len(inventory_periods) >= 2:
        return (
            ("cost_of_goods_sold", "cost of goods sold", current_period),
            *(
                (f"inventory:{period}", "inventory", period)
                for period in inventory_periods
            ),
        )
    return same_period_specs(
        current_period,
        ("cost_of_goods_sold", "cost of goods sold"),
        ("average_inventory", "inventory"),
    )


def same_period_specs(
    period: str,
    *specs: tuple[str, str],
) -> FinanceOperandSpecs:
    return tuple((slot_id, metric, period) for slot_id, metric in specs)


def finance_target_period(question: str, periods: list[str]) -> str:
    named_formula_period = re.search(
        r"\b(?:fy\s*)?((?:19|20)\d{2})\s+"
        r"(?:fixed\s+asset\s+turnover|net\s+fixed\s+asset\s+turnover|"
        r"revenue|net\s+sales)\b",
        question,
    )
    if named_formula_period is not None:
        return named_formula_period.group(1)
    formula_period = re.search(
        r"\b(?:fy\s*)?((?:19|20)\d{2})\s+"
        r"(?:cogs|cost\s+of\s+(?:goods|products)\s+sold)\b",
        question,
    )
    if formula_period is not None:
        return formula_period.group(1)
    explicit = re.search(
        r"\b(?:as\s+of|during|for|in)\s+(?:fy\s*)?((?:19|20)\d{2})\b",
        question,
    )
    if explicit is not None:
        return explicit.group(1)
    change = re.search(
        r"\bfrom\s+(?:fy\s*)?((?:19|20)\d{2})\s+"
        r"(?:through|to)\s+(?:fy\s*)?((?:19|20)\d{2})\b",
        question,
    )
    if change is not None:
        return change.group(2)
    return periods[-1] if periods else ""


def is_finance_segment_comparison(question: str) -> bool:
    lowered = str(question or "").lower()
    return (
        "segment" in lowered
        and bool(re.search(r"\b(?:increase|decrease|grew|growth)\b", lowered))
        and bool(re.search(r"\b(?:most|least|largest|smallest)\b", lowered))
    )


def finance_comparison_excluded_entities(question: str) -> list[str]:
    match = re.search(
        r"\bexcluding\s+([a-z][a-z0-9 &-]*?)(?:,|\bin\b|\bwhich\b|$)",
        str(question or "").lower(),
    )
    return [match.group(1).strip()] if match else []


def finance_metrics_in_question(question: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    for canonical, aliases in FINANCE_METRIC_ALIASES.items():
        alias_positions = [
            (question.find(alias), alias)
            for alias in aliases
            if question.find(alias) >= 0
        ]
        if not alias_positions:
            continue
        position, matched_alias = min(alias_positions)
        metric = (
            "revenue"
            if canonical == "net sales" and matched_alias == "revenue"
            else canonical
        )
        matches.append((position, metric))
    ordered = [
        metric
        for _position, metric in sorted(matches)
        if metric != "operating cash flow" or "free cash flow" not in question
    ]
    if "net property plant and equipment" in ordered:
        ordered = [
            metric for metric in ordered if metric != "property plant and equipment"
        ]
    if "total current assets" in ordered:
        ordered = [metric for metric in ordered if metric != "current assets"]
    return ordered
