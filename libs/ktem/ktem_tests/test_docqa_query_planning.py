from ktem.docqa.query_planning import (
    bind_evidence_slots,
    build_query_plan,
    missing_slot_queries,
    retrieval_budget,
)


def test_numeric_comparison_plan_has_distinct_required_period_operands():
    plan = build_query_plan(
        "What was the percentage change in revenue from 2021 to 2022?",
        answer_type="numeric",
        verification_domain="finance",
    )

    assert plan.answer_type == "numeric"
    assert plan.question_type == "multi_period_numeric"
    assert [slot.period for slot in plan.evidence_slots] == ["2021", "2022"]
    assert all(slot.required for slot in plan.evidence_slots)
    assert all(slot.role == "operand" for slot in plan.evidence_slots)
    assert plan.max_retrieval_rounds == 2
    assert retrieval_budget(plan) == {"max_items": 16, "max_pages": 6}


def test_slot_binding_and_missing_queries_only_target_unfilled_operand():
    plan = build_query_plan(
        "What was the percentage change in revenue from 2021 to 2022?",
        answer_type="numeric",
        verification_domain="finance",
    )
    bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "revenue-2021",
                "text": "Revenue was $10 million in 2021.",
                "page_label": "4",
                "modality": "table",
            }
        ],
    )

    assert bound.evidence_slots[0].status == "filled"
    assert bound.evidence_slots[0].evidence_ids == ("revenue-2021",)
    assert bound.evidence_slots[1].status == "missing"
    assert missing_slot_queries(bound) == ["revenue 2022"]


def test_numeric_slot_rejects_topical_text_without_bound_value():
    plan = build_query_plan(
        "What was the percentage change in revenue from 2021 to 2022?",
        answer_type="numeric",
        verification_domain="finance",
    )
    bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "revenue-commentary",
                "text": "Revenue improved during 2021.",
                "page_label": "4",
                "modality": "text",
            }
        ],
    )

    assert all(slot.status == "missing" for slot in bound.evidence_slots)
    assert missing_slot_queries(bound) == ["revenue 2021", "revenue 2022"]


def test_long_form_plan_uses_long_answer_budget_without_numeric_slots():
    plan = build_query_plan(
        "Explain why the paper introduces a retrieval reranker.",
        answer_type="free_text",
    )

    assert plan.question_type == "long_form"
    assert retrieval_budget(plan) == {"max_items": 12, "max_pages": 5}


def test_causal_finance_question_takes_precedence_over_numeric_surface_terms():
    plan = build_query_plan(
        (
            "What drove the reduction in SG&A expense as a percent of net "
            "sales in FY2023?"
        ),
        answer_type="extractive",
        verification_domain="finance",
    )

    assert plan.answer_type == "extractive"
    assert plan.question_type == "long_form"
    assert plan.evidence_slots == ()


def test_generic_numeric_slots_bind_distinct_canonical_evidence():
    plan = build_query_plan(
        "Calculate the ratio of operating income to net sales.",
        answer_type="numeric",
        verification_domain="finance",
    )
    bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "operating-income",
                "text": "Operating income was $20 million.",
                "modality": "table",
            },
            {
                "evidence_id": "net-sales",
                "text": "Net sales were $100 million.",
                "modality": "table",
            },
        ],
    )

    assert len(bound.evidence_slots) == 2
    assert [slot.metric for slot in bound.evidence_slots] == [
        "operating income",
        "net sales",
    ]
    assert bound.evidence_slots[0].evidence_ids
    assert bound.evidence_slots[1].evidence_ids
    assert not (
        set(bound.evidence_slots[0].evidence_ids)
        & set(bound.evidence_slots[1].evidence_ids)
    )


def test_direct_finance_value_plan_has_one_metric_slot():
    plan = build_query_plan(
        "What is PepsiCo's FY2021 capital expenditure amount in USD billions?",
        answer_type="extractive",
        verification_domain="finance",
    )

    assert plan.answer_type == "numeric"
    assert [
        (slot.slot_id, slot.metric, slot.period) for slot in plan.evidence_slots
    ] == [("operand:capital_expenditure:2021", "capital expenditure", "2021")]
    assert plan.subqueries == ("capital expenditure 2021",)


def test_free_cash_flow_plan_retrieves_both_formula_operands():
    plan = build_query_plan(
        "What was free cash flow in FY2022?",
        answer_type="numeric",
        verification_domain="finance",
    )

    assert [(slot.slot_id, slot.metric) for slot in plan.evidence_slots] == [
        ("operand:operating_cash_flow", "operating cash flow"),
        ("operand:capital_expenditure", "capital expenditure"),
    ]
    assert all(slot.period == "2022" for slot in plan.evidence_slots)


def test_inventory_turnover_plan_uses_distinct_average_inventory_periods():
    plan = build_query_plan(
        (
            "What was inventory turnover in FY2022 using cost of goods sold "
            "and average inventory from FY2021 and FY2022?"
        ),
        answer_type="numeric",
        verification_domain="finance",
    )

    assert [(slot.metric, slot.period) for slot in plan.evidence_slots] == [
        ("cost of goods sold", "2022"),
        ("inventory", "2021"),
        ("inventory", "2022"),
    ]
