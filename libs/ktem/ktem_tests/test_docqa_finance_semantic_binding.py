from ktem.docqa.element_parser import parse_element_index_records
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.financial_statement_identity import financial_statement_identity
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_planning import build_query_plan


def test_inventory_turnover_rejects_held_for_sale_inventory_binding():
    question = (
        "What is FY2019 inventory turnover, calculated as FY2019 COGS "
        "divided by average FY2018 and FY2019 inventory?"
    )
    plan = build_query_plan(
        question,
        answer_type="numeric",
        verification_domain="finance",
    )

    answer = finance_numeric_answer(
        question,
        [
            {
                "evidence_id": "income-statement",
                "text": (
                    "Consolidated Statements of Income (in millions)\n"
                    "2019 2018\nCost of products sold 16,830 17,347"
                ),
            },
            {
                "evidence_id": "held-for-sale",
                "text": (
                    "Assets held for sale (in millions)\n"
                    "2019 2018\nInventories 21 92"
                ),
            },
        ],
        query_plan=plan.as_dict(),
    )

    assert answer is not None
    assert answer.answer == ""
    assert answer.attempt_status == "verification_failed"
    assert any(
        error.startswith("required_slot_missing:operand:inventory")
        for error in answer.calculation_verification["errors"]
    )


def test_consolidated_statement_scope_is_not_overridden_by_one_held_for_sale_row():
    statement_kind, scope = financial_statement_identity(
        """
        The Kraft Heinz Company Consolidated Balance Sheets
        2019 2018
        Inventories 2,750 2,500
        Assets held for sale 21 92
        Total current assets 8,000 7,500
        """
    )

    assert statement_kind == "balance_sheet"
    assert scope == "consolidated"


def test_consolidated_statements_of_earnings_are_income_statement_identity():
    statement_kind, scope = financial_statement_identity(
        "General Mills Consolidated Statements of Earnings (In Millions)"
    )

    assert statement_kind == "income_statement"
    assert scope == "consolidated"


def test_statements_of_earnings_heading_propagates_to_cogs_and_sales_cells():
    text = (
        "GENERAL MILLS, INC. AND SUBSIDIARIES\n"
        "CONSOLIDATED STATEMENTS OF EARNINGS (In Millions)\n"
        "Fiscal Year\n"
        "2019 2018\n"
        "Net sales 16,865.2 15,740.4\n"
        "Cost of sales 11,108.4 10,304.8\n"
    )
    records = parse_element_index_records(
        doc_id="general-mills-earnings",
        file_id="general-mills",
        file_name="GENERALMILLS_2019_10K.pdf",
        page_label="53",
        text=text,
        metadata={"type": "image"},
    )
    cells = [record for record in records if record.get("evidence_level") == "cell"]

    assert cells
    assert {
        (cell["row_label"], cell["period"], cell["statement_kind"]) for cell in cells
    } == {
        ("Net sales", "2019", "income_statement"),
        ("Net sales", "2018", "income_statement"),
        ("Cost of sales", "2019", "income_statement"),
        ("Cost of sales", "2018", "income_statement"),
    }

    question = (
        "What is the FY2019 cash conversion cycle (CCC) for General Mills? CCC "
        "is defined as: DIO + DSO - DPO. DIO is defined as: 365 * (average "
        "inventory between FY2018 and FY2019) / (FY2019 COGS). DSO is defined "
        "as: 365 * (average accounts receivable between FY2018 and FY2019) / "
        "(FY2019 Revenue). DPO is defined as: 365 * (average accounts payable "
        "between FY2018 and FY2019) / (FY2019 COGS + change in inventory between "
        "FY2018 and FY2019). Use the income statement and balance sheet."
    )
    plan = build_query_plan(
        question,
        answer_type="numeric",
        verification_domain="finance",
    )
    bound = bind_evidence_slots(plan, cells)
    slots = {slot.slot_id: slot for slot in bound.evidence_slots}

    for slot_id in ("operand:cost_of_goods_sold:2019", "operand:net_sales:2019"):
        assert slots[slot_id].status == "filled"
        assert slots[slot_id].evidence_ids


def test_inventory_turnover_binds_cogs_to_explicit_formula_year():
    question = (
        "What is FY2019 inventory turnover, calculated as FY2019 COGS "
        "divided by average FY2018 and FY2019 inventory?"
    )
    plan = build_query_plan(
        question,
        answer_type="numeric",
        verification_domain="finance",
    )

    answer = finance_numeric_answer(
        question,
        [
            {
                "evidence_id": "income-statement",
                "text": (
                    "Consolidated Statements of Income (in millions)\n"
                    "2019 2018\nCost of products sold 16,830 17,347"
                ),
            },
            {
                "evidence_id": "balance-sheet",
                "text": (
                    "Consolidated Balance Sheets (in millions)\n"
                    "2019 2018\nInventories 2,750 2,500"
                ),
            },
        ],
        query_plan=plan.as_dict(),
    )

    assert answer is not None
    assert answer.calculation_verification["valid"] is True
    assert answer.inputs["cost_of_goods_sold"] == 16830.0
    cogs = next(
        operand
        for operand in answer.calculation_plan["operands"]
        if operand["operand_id"] == "cost_of_goods_sold"
    )
    assert cogs["period"] == "2019"
