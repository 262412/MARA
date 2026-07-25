from decimal import Decimal
from typing import Any

from ktem.docqa.calculation_plan import verify_calculation_plan
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.financial_table import find_financial_cell, parse_financial_table_cells

LOCKHEED_BALANCE_SHEET = """
CONSOLIDATED BALANCE SHEETS
(In millions, except per share data) 2021 2020 2019 2018 2017
Current assets 20,991 19,378 17,095 15,279 14,642
Current liabilities 15,173 15,911 14,402 14,398 13,551
Total assets 50,873 50,710 47,528 44,876 46,521
"""


def _table_item(text: str = LOCKHEED_BALANCE_SHEET) -> dict[str, object]:
    return {
        "element_id": "balance-sheet-table",
        "canonical_id": "report#table:balance-sheet",
        "source_id": "LOCKHEEDMARTIN_2021_10K",
        "page_label": "68",
        "element_type": "table",
        "text": text,
    }


def test_financial_table_parser_emits_metric_period_cell_identity():
    cells = parse_financial_table_cells(_table_item())
    current_assets = find_financial_cell(
        [_table_item()],
        aliases=("total current assets", "current assets"),
        period="2021",
    )

    assert len(cells) == 15
    assert current_assets is not None
    assert current_assets.value == Decimal("20991")
    assert current_assets.row_label == "Current assets"
    assert current_assets.column_label == "2021"
    assert current_assets.period == "2021"
    assert current_assets.scale == "million"
    assert current_assets.cell_id.endswith("#row:current-assets#column:2021")


def test_working_capital_operands_bind_to_distinct_rows_and_requested_period():
    answer = finance_numeric_answer(
        "What was working capital in 2021, in USD millions?",
        [_table_item()],
    )

    assert answer is not None
    assert answer.answer == "$5,818.0 million"
    assert answer.calculation_verification["valid"] is True
    operands = {
        operand["operand_id"]: operand
        for operand in answer.calculation_plan["operands"]
    }
    assert operands["left"]["row_label"] == "Current assets"
    assert operands["left"]["column_label"] == "2021"
    assert operands["right"]["row_label"] == "Current liabilities"
    assert operands["right"]["column_label"] == "2021"
    assert operands["left"]["cell_id"] != operands["right"]["cell_id"]

    verification = verify_calculation_plan(
        _plan_from_answer(answer),
        [_table_item(LOCKHEED_BALANCE_SHEET.replace("20,991", "20,990"))],
        question="What was working capital in 2021, in USD millions?",
    )
    assert verification.valid is False
    assert "operand_cell_mismatch:left" in verification.errors


def test_free_cash_flow_uses_the_requested_period_column_not_result_distractor():
    item = _table_item(
        """
        CONSOLIDATED STATEMENTS OF CASH FLOWS
        (In millions) 2020 2019
        Net cash provided by operating activities 3,676.2 3,100.0
        Capital expenditures (460.8) (400.0)
        Free cash flow 3,215.4 2,700.0
        """
    )

    answer = finance_numeric_answer(
        "What was free cash flow in 2020, in USD millions?",
        [item],
    )

    assert answer is not None
    assert answer.answer == "$3,215.4 million"
    assert answer.inputs == {
        "operating_cash_flow": 3676.2,
        "capital_expenditure": -460.8,
    }
    operands = {
        operand["operand_id"]: operand
        for operand in answer.calculation_plan["operands"]
    }
    assert operands["operating_cash_flow"]["row_label"].startswith("Net cash provided")
    assert operands["capital_expenditure"]["row_label"] == "Capital expenditures"
    assert operands["capital_expenditure"]["column_label"] == "2020"


def _plan_from_answer(answer):
    from ktem.docqa.calculation_plan import (
        CalculationOperand,
        CalculationPlan,
        CalculationStep,
    )

    payload = answer.calculation_plan
    return CalculationPlan(
        operands=tuple(
            CalculationOperand(
                **_operand_payload(item),
            )
            for item in payload["operands"]
        ),
        steps=tuple(
            CalculationStep(
                step_id=item["step_id"],
                operator=item["operator"],
                input_ids=tuple(item["input_ids"]),
                constant=(
                    None if item["constant"] is None else Decimal(item["constant"])
                ),
                constant_source=item["constant_source"],
                rounding_places=item["rounding_places"],
            )
            for item in payload["steps"]
        ),
        result_step_id=payload["result_step_id"],
        answer_unit=payload["answer_unit"],
        answer_scale=payload["answer_scale"],
    )


def _operand_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "value": Decimal(item["value"]),
    }
