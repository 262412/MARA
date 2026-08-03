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
    assert all(slot.required_for_retrieval for slot in plan.evidence_slots)
    assert all(slot.required_for_execution for slot in plan.evidence_slots)
    assert all(slot.required_for_verification for slot in plan.evidence_slots)
    assert plan.max_retrieval_rounds == 2
    assert retrieval_budget(plan) == {"max_items": 16, "max_pages": 6}
    assert plan.plan_id.startswith("plan:")


def test_boolean_question_builds_verification_only_proposition_slot():
    plan = build_query_plan(
        "Does the proposed model outperform the baseline?",
        answer_type="boolean",
        verification_domain="qasper",
    )

    [slot] = plan.evidence_slots
    assert slot.slot_id == "support:boolean_proposition"
    assert slot.role == "support"
    assert slot.required_for_retrieval is False
    assert slot.required_for_verification is True
    assert slot.query == "Does the proposed model outperform the baseline?"


def test_qasper_boolean_form_takes_precedence_over_causal_word() -> None:
    plan = build_query_plan(
        "Do they demonstrate why interdisciplinary insights are important?",
        answer_type="qasper_qa",
        verification_domain="qasper",
    )

    assert plan.answer_type == "boolean"
    assert plan.question_type == "simple_fact"
    [slot] = plan.evidence_slots
    assert slot.statement_kind == "boolean_proposition"


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
                **_finance_cell(
                    "revenue-2021",
                    "Revenue",
                    "2021",
                    "10",
                    "income_statement",
                ),
                "text": "Revenue was $10 million in 2021.",
                "page_label": "4",
            }
        ],
    )

    assert bound.evidence_slots[0].status == "filled"
    assert bound.evidence_slots[0].evidence_ids == ("cell::revenue-2021",)
    assert bound.evidence_slots[1].status == "missing"
    assert missing_slot_queries(bound) == [
        "revenue consolidated statements of income 2022"
    ]


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
    assert missing_slot_queries(bound) == [
        "revenue consolidated statements of income 2021",
        "revenue consolidated statements of income 2022",
    ]


def test_finance_fact_slot_requires_exact_metric_not_adjusted_ebit_prefix():
    plan = build_query_plan(
        "What was adjusted non-GAAP EBITDA for FY2023?",
        answer_type="extractive",
        verification_domain="finance",
    )
    bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "full-year-adjusted-ebit",
                "text": (
                    "Fiscal 2023 Full Year Highlights. "
                    "Adjusted EBIT was $1,608 million."
                ),
                "page_label": "1",
                "period_kind": "fiscal_year",
                "modality": "text",
            }
        ],
    )

    [adjusted_ebitda] = bound.evidence_slots
    assert adjusted_ebitda.metric == "adjusted ebitda"
    assert adjusted_ebitda.status == "missing"


def test_finance_fact_slot_requires_atomic_value_evidence():
    plan = build_query_plan(
        "What was adjusted non-GAAP EBITDA for FY2023?",
        answer_type="extractive",
        verification_domain="finance",
    )
    page_bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "full-year-page",
                "evidence_level": "page",
                "text": "FY2023 adjusted EBITDA was $2,018 million.",
                "page_label": "1",
                "period_kind": "fiscal_year",
                "modality": "text",
            }
        ],
    )
    cell_bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "adjusted-ebitda-cell",
                "cell_id": "adjusted-ebitda-cell",
                "evidence_level": "cell",
                "row_label": "Adjusted EBITDA",
                "column_label": "2023",
                "period": "2023",
                "period_kind": "fiscal_year",
                "value": "2018",
                "scale": "million",
                "text": "Adjusted EBITDA 2023 fiscal_year 2018 million",
                "modality": "table",
            }
        ],
    )

    assert page_bound.evidence_slots[0].status == "missing"
    assert cell_bound.evidence_slots[0].status == "filled"
    assert cell_bound.evidence_slots[0].evidence_ids == ("cell::adjusted-ebitda-cell",)


def test_numeric_slot_rejects_period_values_without_metric_support():
    plan = build_query_plan(
        (
            "What was the average cost of goods sold as a percent of revenue "
            "from 2016 through 2018?"
        ),
        answer_type="numeric",
        verification_domain="finance",
    )
    bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "unrelated-period-table",
                "text": "Headcount was 46 in 2016, 4 in 2017, and 25 in 2018.",
                "page_label": "16",
                "modality": "table",
            }
        ],
    )

    assert all(slot.status == "missing" for slot in bound.evidence_slots)


def test_cost_of_goods_sold_slot_rejects_alias_tokens_scattered_in_prose():
    plan = build_query_plan(
        "What was inventory turnover in FY2018 using cost of goods sold?",
        answer_type="numeric",
        verification_domain="finance",
    )
    bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "pension-distractor",
                "text": (
                    "In 2018 compensation cost was $7 million. Finished goods "
                    "were discussed elsewhere, and unrelated assets were sold."
                ),
                "modality": "text",
            }
        ],
    )

    cogs = next(
        slot for slot in bound.evidence_slots if slot.metric == "cost of goods sold"
    )
    assert cogs.status == "missing"


def test_cost_of_products_sold_is_a_bound_cogs_table_alias():
    plan = build_query_plan(
        "What was inventory turnover in FY2019 using cost of goods sold?",
        answer_type="numeric",
        verification_domain="finance",
    )
    bound = bind_evidence_slots(
        plan,
        [
            {
                **_finance_cell(
                    "cogs-2019",
                    "Cost of products sold",
                    "2019",
                    "16830",
                    "income_statement",
                ),
                "text": (
                    "Consolidated Statements of Income. Cost of products "
                    "sold 2019 16,830 million."
                ),
            }
        ],
    )

    cogs = next(
        slot for slot in bound.evidence_slots if slot.metric == "cost of goods sold"
    )
    assert cogs.status == "filled"
    assert cogs.evidence_ids == ("cell::cogs-2019",)


def test_multi_period_percentage_of_revenue_plan_requires_both_metrics():
    plan = build_query_plan(
        (
            "What was the three year average of cost of goods sold as a % of "
            "revenue from FY2016 to FY2018?"
        ),
        answer_type="numeric",
        verification_domain="finance",
    )

    assert [(slot.metric, slot.period) for slot in plan.evidence_slots] == [
        ("cost of goods sold", "2016"),
        ("net sales", "2016"),
        ("cost of goods sold", "2017"),
        ("net sales", "2017"),
        ("cost of goods sold", "2018"),
        ("net sales", "2018"),
    ]


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
    assert len(plan.evidence_slots) == 1
    assert plan.evidence_slots[0].slot_id == "support:primary"
    assert plan.evidence_slots[0].required_for_execution is False
    assert plan.evidence_slots[0].query == (
        "What drove the reduction in SG&A expense as a percent of net "
        "sales in FY2023?"
    )


def test_simple_fact_plan_reserves_primary_support_evidence():
    plan = build_query_plan(
        "What industry does AMCOR primarily operate in?",
        answer_type="extractive",
        verification_domain="finance",
    )

    assert plan.question_type == "simple_fact"
    assert len(plan.evidence_slots) == 1
    assert plan.evidence_slots[0].slot_id == "support:primary"
    assert plan.evidence_slots[0].required_for_retrieval is True
    assert plan.evidence_slots[0].required_for_verification is True
    assert plan.evidence_slots[0].query == (
        "What industry does AMCOR primarily operate in?"
    )


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
                **_finance_cell(
                    "operating-income",
                    "Operating income",
                    "",
                    "20",
                    "income_statement",
                ),
                "text": "Operating income was $20 million.",
            },
            {
                **_finance_cell(
                    "net-sales",
                    "Net sales",
                    "",
                    "100",
                    "income_statement",
                ),
                "text": "Net sales were $100 million.",
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
        (slot.slot_id, slot.role, slot.metric, slot.period, slot.scale)
        for slot in plan.evidence_slots
    ] == [
        (
            "operand:capital_expenditure:2021",
            "operand",
            "capital expenditure",
            "2021",
            "",
        ),
        ("dimension:scale", "dimension", "", "", ""),
    ]
    assert plan.subqueries == (
        "capital expenditure capital spending consolidated statement of cash flows 2021",
        "tabular dollars unit scale convention",
    )


def test_direct_net_ppe_plan_uses_canonical_finance_metric():
    plan = build_query_plan(
        (
            "What is Boeing's year end FY2018 net property, plant, and "
            "equipment in USD millions?"
        ),
        answer_type="extractive",
        verification_domain="finance",
    )

    assert plan.answer_type == "numeric"
    assert [(slot.metric, slot.period) for slot in plan.evidence_slots] == [
        ("net property plant and equipment", "2018"),
        ("", ""),
    ]


def test_total_current_assets_slot_rejects_other_current_assets_prose():
    plan = build_query_plan(
        "How much total current assets did Nike have at the end of FY2019?",
        answer_type="numeric",
        verification_domain="finance",
    )
    bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "other-current-assets",
                "text": ("Other current assets increased by $95 million in FY2019."),
                "modality": "text",
            }
        ],
    )

    operand = next(slot for slot in bound.evidence_slots if slot.role == "operand")
    assert operand.metric == "total current assets"
    assert operand.status == "missing"
    assert (
        "total current assets consolidated balance sheet 2019"
        in missing_slot_queries(bound)
    )


def test_net_ppe_slot_rejects_cash_flow_additions():
    plan = build_query_plan(
        (
            "What is Boeing's year end FY2018 net property, plant, and "
            "equipment in USD millions?"
        ),
        answer_type="numeric",
        verification_domain="finance",
    )
    bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "cash-flow-additions",
                "text": (
                    "Additions to property, plant and equipment were "
                    "$1,722 million in 2018."
                ),
                "modality": "table",
            }
        ],
    )

    operand = next(slot for slot in bound.evidence_slots if slot.role == "operand")
    assert operand.metric == "net property plant and equipment"
    assert operand.status == "missing"


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
    assert plan.constraints["requires_structure"] is True


def test_finance_numeric_slots_do_not_bind_page_level_multi_value_evidence():
    plan = build_query_plan(
        "What was free cash flow in FY2022?",
        answer_type="numeric",
        verification_domain="finance",
    )
    bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "page-17",
                "evidence_level": "page",
                "modality": "table",
                "text": (
                    "2022 2021\nOperating cash flow 3,676.2 3,100.0\n"
                    "Capital expenditure 460.8 420.0\nFree cash flow 3,215.4"
                ),
            }
        ],
    )

    assert all(slot.status == "missing" for slot in bound.evidence_slots)


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
    assert [
        (slot.statement_kind, slot.financial_scope) for slot in plan.evidence_slots
    ] == [
        ("income_statement", "consolidated"),
        ("balance_sheet", "consolidated"),
        ("balance_sheet", "consolidated"),
    ]


def test_inventory_turnover_uses_explicit_cogs_year_not_period_order():
    plan = build_query_plan(
        (
            "What is FY2019 inventory turnover, calculated as FY2019 COGS "
            "divided by average FY2018 and FY2019 inventory?"
        ),
        answer_type="numeric",
        verification_domain="finance",
    )

    assert [(slot.metric, slot.period) for slot in plan.evidence_slots] == [
        ("cost of goods sold", "2019"),
        ("inventory", "2018"),
        ("inventory", "2019"),
    ]


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
