from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.financial_statement_identity import financial_statement_identity
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
