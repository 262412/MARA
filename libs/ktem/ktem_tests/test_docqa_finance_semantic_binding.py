from ktem.docqa.finance_numeric_answer import finance_numeric_answer
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
