from decimal import Decimal
from typing import Any

from ktem.docqa.calculation_evidence_identity import calculation_evidence_items
from ktem.docqa.calculation_plan import verify_calculation_plan
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.finance_scale import source_scale_evidence
from ktem.docqa.financial_table import find_financial_cell, parse_financial_table_cells
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan

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
    assert current_assets.cell_id.endswith("#row:1#column:1")
    assert current_assets.physical_identity.row_index == 1
    assert current_assets.semantic_key.metric == "current_assets"


def test_file_id_only_table_uses_file_id_for_physical_cell_identity():
    item = {
        "evidence_id": "element:balance-sheet",
        "file_id": "report-file",
        "page_label": "68",
        "element_type": "table",
        "table_id": "balance-sheet",
        "text": "Consolidated Balance Sheets (in millions)\n"
        "2021 2020\nTotal current assets 19,815 19,378",
    }

    cell = next(
        cell for cell in parse_financial_table_cells(item) if cell.period == "2021"
    )

    assert cell.source_id == "report-file"
    assert cell.physical_identity.source_id == "report-file"
    assert "source:unknown" not in cell.cell_id


def test_financial_table_parser_skips_numeric_descriptor_columns():
    item = _table_item(
        """
        PROPERTY, PLANT AND EQUIPMENT
        At December 31, Lives (years) 2021 2020
        Buildings and equipment 7 to 45 33,361 32,933
        """
    )

    cell = find_financial_cell(
        [item],
        aliases=("buildings and equipment",),
        period="2021",
    )

    assert cell is not None
    assert cell.value == Decimal("33361")
    assert cell.row_label == "Buildings and equipment"


def test_financial_table_parser_recovers_value_first_wrapped_rows():
    item = _table_item(
        """
        CONSOLIDATED STATEMENTS OF FINANCIAL POSITION
        December 31,
        2018 2017 Assets
        Cash and cash equivalents
        $7,637 $8,813 Short-term and other investments
        927 1,179 Property, plant and equipment, net
        12,645 12,672 Goodwill
        7,840 5,559
        """
    )

    cell = find_financial_cell(
        [item],
        aliases=("property, plant and equipment, net",),
        period="2018",
        period_kind="fiscal_year",
    )

    assert cell is not None
    assert cell.value == Decimal("12645")
    assert cell.row_label == "Property, plant and equipment, net"
    assert cell.column_label == "2018"
    assert cell.cell_id.endswith("#row:3#column:1")
    assert cell.semantic_key.metric == "property_plant_and_equipment_net"


def test_financial_table_parser_keeps_period_kind_per_table_section():
    item = _table_item(
        """
        Reconciliation of adjusted EBITDA
        Three Months Ended June 30, 2023 2022
        Adjusted EBITDA 540 609
        Twelve Months Ended June 30, 2023 2022
        Adjusted EBITDA 2,018 1,948
        """
    )

    fiscal = find_financial_cell(
        [item],
        aliases=("adjusted ebitda",),
        period="2023",
        period_kind="fiscal_year",
    )
    quarter = find_financial_cell(
        [item],
        aliases=("adjusted ebitda",),
        period="2023",
        period_kind="quarter",
    )

    assert fiscal is not None
    assert fiscal.value == Decimal("2018")
    assert fiscal.period_kind == "fiscal_year"
    assert quarter is not None
    assert quarter.value == Decimal("540")
    assert quarter.period_kind == "quarter"


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
        "capital_expenditure": 460.8,
    }
    operands = {
        operand["operand_id"]: operand
        for operand in answer.calculation_plan["operands"]
    }
    assert operands["operating_cash_flow"]["row_label"].startswith("Net cash provided")
    assert operands["capital_expenditure"]["row_label"] == "Capital expenditures"
    assert operands["capital_expenditure"]["column_label"] == "2020"


def test_free_cash_flow_preserves_table_boundary_before_numeric_source_name():
    cash_flow = {
        "evidence_id": "general-mills-page-17",
        "source_id": "GENERALMILLS_2020_10K",
        "page_label": "17",
        "element_type": "table",
        "text": """
        In Millions, Except Per Share Data, Percentages and Ratios
        2020 2019 2018 2017 2016
        Net cash provided by operating activities 3,676.2 2,807.0 2,841.0 2,415.2 2,764.2
        Capital expenditures 460.8 537.6 622.7 684.4 729.3
        """.strip(),
    }
    numeric_source_name = {
        "evidence_id": "general-mills-page-95",
        "source_id": "GENERALMILLS_2020_10K",
        "source_name": "GENERALMILLS_2020_10K.pdf",
        "page_label": "95",
        "text": "95 Glossary 2020 definitions.",
    }

    answer = finance_numeric_answer(
        (
            "What is FY2020 free cash flow, defined as operating cash flow "
            "minus capital expenditures? Answer in USD millions."
        ),
        [cash_flow, numeric_source_name],
    )

    assert answer is not None
    assert answer.answer == "$3,215.4 million"
    assert answer.inputs["capital_expenditure"] == 460.8
    assert answer.calculation_verification["valid"] is True


def test_free_cash_flow_rebuilds_inputs_from_authoritative_bound_operands():
    question = (
        "What is FY2020 free cash flow, defined as operating cash flow minus "
        "capital expenditures? Answer in USD millions."
    )
    misleading_page = {
        "evidence_id": "narrative",
        "source_id": "GENERALMILLS_2020_10K",
        "page_label": "20",
        "text": (
            "In FY2020 operating cash flow was 3,676.2 million and an earlier "
            "capital spending estimate was 684.4 million."
        ),
    }
    cash_flow = _table_item(
        """
        CONSOLIDATED STATEMENTS OF CASH FLOWS
        (In millions) 2020 2019
        Net cash provided by operating activities 3,676.2 3,100.0
        Purchases of land, buildings, and equipment (460.8) (400.0)
        """
    )
    evidence: list[dict[str, Any]] = [misleading_page, cash_flow]
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        evidence,
    )

    answer = finance_numeric_answer(question, evidence, query_plan=plan.as_dict())

    assert answer is not None
    assert answer.answer == "$3,215.4 million"
    assert answer.inputs == {
        "operating_cash_flow": 3676.2,
        "capital_expenditure": 460.8,
    }
    operands = {
        operand["operand_id"]: operand
        for operand in answer.calculation_plan["operands"]
    }
    assert operands["capital_expenditure"]["value"] == "460.8"
    assert operands["capital_expenditure"]["value_semantics"] == "positive_magnitude"
    assert answer.calculation_plan["steps"][0]["operator"] == "subtract"
    assert answer.calculation_execution["value"] == "3215.4"


def test_consolidating_table_preserves_column_scope_path():
    consolidating = _table_item(
        """
        The Kraft Heinz Company
        Condensed Consolidating Statements of Income
        For the Year Ended December 28, 2019
        (in millions)
        Parent Guarantor Subsidiary Issuer Non-Guarantor
        Subsidiaries Eliminations Consolidated
        Net sales — 16,852 8,588 (463) 24,977
        Cost of products sold — 11,042 6,251 (463) 16,830
        """
    )

    cells = [
        cell
        for cell in parse_financial_table_cells(consolidating)
        if cell.row_label == "Cost of products sold"
    ]

    assert len(cells) == 5
    assert [cell.financial_scope for cell in cells] == [
        "parent",
        "guarantor_subsidiary_issuer",
        "non_guarantor_subsidiaries",
        "eliminations",
        "consolidated",
    ]
    assert cells[-1].column_header_path == ("Consolidated", "2019")
    assert cells[-1].value == Decimal("16830")


def test_primary_consolidated_statement_outranks_consolidating_schedule():
    consolidating = _table_item(
        """
        Condensed Consolidating Statements of Income
        For the Year Ended December 28, 2019
        (in millions)
        Parent Guarantor Subsidiary Issuer Non-Guarantor
        Subsidiaries Eliminations Consolidated
        Cost of products sold — 11,042 6,251 (463) 16,830
        """
    )
    primary = {
        **_table_item(
            """
            Consolidated Statements of Income
            (in millions) 2019 2018
            Cost of products sold 16,830 17,347
            """
        ),
        "evidence_id": "primary-income-statement",
        "element_id": "primary-income-statement",
        "table_id": "primary-income-statement",
    }

    cell = find_financial_cell(
        [consolidating, primary],
        aliases=("cost of products sold",),
        period="2019",
        statement_kind="income_statement",
        financial_scope="consolidated",
    )

    assert cell is not None
    assert cell.value == Decimal("16830")
    assert cell.table_id == "primary-income-statement"


def test_adjusted_ebitda_continuation_table_materializes_atomic_fy2023_cell():
    page = {
        "evidence_id": "amcor-reconciliation-page",
        "source_id": "amcor",
        "source_name": "AMCOR_2023Q4_EARNINGS.pdf",
        "page_label": "12",
        "text": """
        Twelve Months Ended June 30, 2022 Twelve Months Ended June 30, 2023
        ($ million) EBITDA EBIT Net Income EPS EBITDA EBIT Net Income EPS
        Adjusted EBITDA, EBIT, Net income and EPS 2,117 1,701 1,224 80.5 2,018 1,608 1,089 73.3
        Reconciliation of adjusted growth to comparable constant currency growth
        Adjusted EBITDA 2,117 2,018
        Adjusted Free Cash Flow 1,066 848
        """,
    }

    items = calculation_evidence_items([page])
    plan = bind_evidence_slots(
        build_query_plan(
            "What was AMCOR's adjusted non-GAAP EBITDA for FY2023?",
            answer_type="numeric",
            verification_domain="finance",
        ),
        items,
    )
    [slot] = [value for value in plan.evidence_slots if value.role == "operand"]

    assert slot.status == "filled"
    [evidence_id] = slot.evidence_ids
    selected = next(item for item in items if identity_of(item).key == evidence_id)
    assert selected["evidence_level"] == "cell"
    assert selected["row_label"] == "Adjusted EBITDA"
    assert selected["period"] == "2023"
    assert selected["value"] == "2018"


def test_quarterly_report_dates_map_to_fiscal_period_cells():
    page = {
        "evidence_id": "best-buy-balance-sheet",
        "source_id": "best-buy",
        "source_name": "BESTBUY_2024Q2_10Q.pdf",
        "page_label": "3",
        "text": """
        Condensed Consolidated Balance Sheets
        $ in millions, except per share amounts (unaudited)
        July 29, 2023 January 28, 2023 July 30, 2022
        Assets
        Cash and cash equivalents $ 1,093 $ 1,874 $ 840
        """,
    }

    cells = [
        cell
        for cell in parse_financial_table_cells(page)
        if cell.row_label == "Cash and cash equivalents"
    ]

    assert [
        (cell.column_label, cell.period, cell.period_kind, cell.value) for cell in cells
    ] == [
        ("July 29, 2023", "2024", "quarter", Decimal("1093")),
        ("January 28, 2023", "2023", "fiscal_year", Decimal("1874")),
        ("July 30, 2022", "2023", "quarter", Decimal("840")),
    ]


def test_financial_table_parser_does_not_treat_bare_period_as_cell_value():
    item = _table_item(
        """
        AS OF MAY 31, 2019 2018
        An increase in prepaid expenses and other current assets on the
        Consolidated Balance Sheets at May 31, 2019 95
        """
    )

    cell = find_financial_cell(
        [item],
        aliases=("current assets",),
        period="2019",
    )

    assert cell is None


def test_finance_scale_can_be_proven_by_same_source_convention_evidence():
    table = {
        "evidence_id": "pepsico-free-cash-flow",
        "canonical_id": "PEPSICO_2021_10K#table:free-cash-flow",
        "source_id": "PEPSICO_2021_10K",
        "page_label": "53",
        "element_type": "table",
        "text": """
        2021 2020
        Net cash provided by operating activities 11,616 10,613
        Capital spending (4,625) (4,240)
        """,
    }
    convention = {
        "evidence_id": "pepsico-tabular-scale",
        "source_id": "PEPSICO_2021_10K",
        "page_label": "40",
        "text": (
            "Unless otherwise noted, tabular dollars are presented in "
            "millions, except per share amounts."
        ),
    }

    answer = finance_numeric_answer(
        "What is FY2021 capital expenditure in USD billions?",
        [table, convention],
    )

    assert answer is not None
    assert answer.answer == "$4.6 billion"
    operand = answer.calculation_plan["operands"][0]
    assert operand["scale"] == "million"
    assert operand["scale_evidence_id"] == "pepsico-tabular-scale"
    assert operand["evidence_identity"].startswith("cell:PEPSICO_2021_10K:")
    assert operand["scale_evidence_identity"] == (
        "evidence:PEPSICO_2021_10K:pepsico-tabular-scale"
    )
    assert answer.calculation_verification["citation_ids"] == (
        operand["evidence_identity"],
        operand["scale_evidence_identity"],
    )


def test_atomic_fact_scale_cannot_be_reused_as_table_scale_convention():
    table = {
        "evidence_id": "pepsico-free-cash-flow",
        "source_id": "PEPSICO_2021_10K",
        "page_label": "53",
        "evidence_level": "element",
        "modality": "table",
        "text": "2021 2020\nCapital spending (4,625) (4,240)",
    }
    unrelated_atomic_fact = {
        "evidence_id": "pepsico-financing-span",
        "source_id": "PEPSICO_2021_10K",
        "page_label": "52",
        "evidence_level": "span",
        "modality": "text",
        "value": "10.8",
        "scale": "billion",
        "text": "Financing activities used $10.8 billion.",
    }

    assert source_scale_evidence(
        table,
        [table, unrelated_atomic_fact],
    ) == ("", "")


def test_ratio_uses_requested_period_instead_of_first_table_column():
    answer = finance_numeric_answer(
        "What was the current ratio in 2020?",
        [_table_item()],
    )

    assert answer is not None
    assert answer.answer == "1.22"
    operands = {
        operand["operand_id"]: operand
        for operand in answer.calculation_plan["operands"]
    }
    assert operands["numerator"]["value"] == "19378.0"
    assert operands["numerator"]["column_label"] == "2020"
    assert operands["denominator"]["value"] == "15911.0"
    assert operands["denominator"]["column_label"] == "2020"


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
