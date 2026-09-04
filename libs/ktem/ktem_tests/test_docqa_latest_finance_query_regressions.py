from ktem.docqa.query_planning import build_query_plan, missing_slot_requests


def test_finance_queries_include_metric_aliases_and_statement_headings() -> None:
    inventory_plan = build_query_plan(
        "What is FY2019 inventory turnover using FY2019 COGS and average "
        "FY2018 and FY2019 inventory?",
        answer_type="numeric",
        verification_domain="finance",
    )
    cogs = next(
        slot
        for slot in inventory_plan.evidence_slots
        if slot.metric == "cost of goods sold"
    )
    assets_plan = build_query_plan(
        "How much total current assets were reported at the end of FY2019?",
        answer_type="numeric",
        verification_domain="finance",
    )
    assets = next(
        slot
        for slot in assets_plan.evidence_slots
        if slot.metric == "total current assets"
    )

    assert "cost of products sold" in cogs.query
    assert "cost of revenues" in cogs.query
    assert "consolidated statements of income" in cogs.query
    assert assets.statement_kind == "balance_sheet"
    assert assets.financial_scope == "consolidated"
    assert "consolidated balance sheet" in assets.query


def test_second_round_finance_query_expands_missing_slot_identity() -> None:
    plan = build_query_plan(
        "What is FY2019 inventory turnover using FY2019 COGS and average "
        "FY2018 and FY2019 inventory?",
        answer_type="numeric",
        verification_domain="finance",
    )
    requests = missing_slot_requests(plan)
    cogs = next(
        item for item in requests if item["slot_id"] == "operand:cost_of_goods_sold"
    )

    assert cogs["query"] != next(
        slot.query for slot in plan.evidence_slots if slot.slot_id == cogs["slot_id"]
    )
    assert "cost of products sold" in cogs["query"]
    assert "2019" in cogs["query"]


def test_adjusted_ebitda_is_numeric_without_a_manifest_answer_type() -> None:
    plan = build_query_plan(
        "What was AMCOR's Adjusted Non GAAP EBITDA for FY2023?",
        verification_domain="finance",
    )

    assert plan.answer_type == "numeric"
    assert any(
        slot.metric == "adjusted ebitda" and slot.required_for_execution
        for slot in plan.evidence_slots
    )
