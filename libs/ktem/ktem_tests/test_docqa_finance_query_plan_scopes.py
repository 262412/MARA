from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan


def test_inventory_slot_distinguishes_balance_from_cash_flow_change():
    plan = build_query_plan(
        "What was inventory turnover in FY2018 using cost of goods sold?",
        answer_type="numeric",
        verification_domain="finance",
    )
    cash_flow_bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "cash-flow-change",
                "text": (
                    "Consolidated Statements of Cash Flows (in millions). "
                    "Changes in current assets and liabilities. "
                    "Inventories (277) (251). 2019 2018."
                ),
                "modality": "table",
            }
        ],
    )
    balance_sheet_bound = bind_evidence_slots(
        plan,
        [
            {
                **_finance_cell(
                    "inventory-2018",
                    "Inventories",
                    "2018",
                    "2500",
                    "balance_sheet",
                ),
                "text": (
                    "Consolidated Balance Sheets. Inventories 2018 " "2,500 million."
                ),
            }
        ],
    )

    cash_flow_inventory = next(
        slot for slot in cash_flow_bound.evidence_slots if slot.metric == "inventory"
    )
    balance_sheet_inventory = next(
        slot
        for slot in balance_sheet_bound.evidence_slots
        if slot.metric == "inventory"
    )
    assert cash_flow_inventory.status == "missing"
    assert balance_sheet_inventory.status == "filled"


def test_inventory_slot_rejects_held_for_sale_subscope():
    plan = build_query_plan(
        (
            "What is FY2019 inventory turnover, calculated as FY2019 COGS "
            "divided by average FY2018 and FY2019 inventory?"
        ),
        answer_type="numeric",
        verification_domain="finance",
    )
    bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "held-for-sale",
                "text": (
                    "Assets held for sale (in millions). 2019 2018. "
                    "Inventories 21 92."
                ),
                "modality": "table",
            }
        ],
    )

    inventories = [slot for slot in bound.evidence_slots if slot.metric == "inventory"]
    assert all(slot.status == "missing" for slot in inventories)


def test_finance_fact_plan_tracks_adjusted_non_gaap_ebitda_period():
    plan = build_query_plan(
        "What was adjusted non-GAAP EBITDA for the twelve months ended 2023?",
        answer_type="extractive",
        verification_domain="finance",
    )

    assert plan.answer_type == "numeric"
    assert [(slot.role, slot.metric, slot.period) for slot in plan.evidence_slots] == [
        ("operand", "adjusted ebitda", "2023")
    ]
    assert plan.subqueries == ("adjusted ebitda non-GAAP reconciliation 2023",)


def test_finance_segment_fact_plan_normalizes_short_fiscal_years():
    plan = build_query_plan(
        (
            "From FY21 to FY22, excluding Embedded, in which AMD reporting "
            "segment did sales proportionally increase the most?"
        ),
        answer_type="extractive",
        verification_domain="finance",
    )

    assert [(slot.role, slot.metric, slot.period) for slot in plan.evidence_slots] == [
        ("support", "net sales", "2021"),
        ("support", "net sales", "2022"),
    ]
    assert plan.question_type == "comparison_argmax"
    assert plan.constraints["comparison_operator"] == "proportional_increase"
    assert plan.constraints["excluded_entities"] == ["embedded"]
    assert all(slot.financial_scope == "segment" for slot in plan.evidence_slots)


def _finance_cell(
    evidence_id: str,
    row_label: str,
    period: str,
    value: str,
    statement_kind: str,
) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "cell_id": evidence_id,
        "evidence_level": "cell",
        "cell_role": "data",
        "row_label": row_label,
        "column_label": period or "FY",
        "period": period,
        "value": value,
        "statement_kind": statement_kind,
        "financial_scope": "consolidated",
        "modality": "table",
    }
