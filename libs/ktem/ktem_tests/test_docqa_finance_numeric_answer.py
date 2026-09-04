from types import SimpleNamespace

from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.reasoning.mara_finance_answering import (
    ensure_finance_numeric_trace,
    route_finance_numeric_answer,
)


def test_finance_numeric_answer_computes_quick_ratio_from_evidence_text():
    answer = finance_numeric_answer(
        "What was 3M's quick ratio in 2022?",
        [
            {
                "evidence_id": "balance-sheet-cell",
                "text": (
                    "Current assets were $14,688 million, inventories were "
                    "$4,962 million, and current liabilities were $10,116 million."
                ),
            }
        ],
    )

    assert answer is not None
    assert answer.answer == "0.96"
    assert answer.confidence >= 0.7
    assert answer.question_type == "quick_ratio"
    assert answer.calculation_plan["contract_id"] == "calculation_plan.v1"
    assert answer.calculation_verification["valid"] is True
    assert answer.calculation_execution["citation_ids"] == [
        "evidence::balance-sheet-cell"
    ]


def test_finance_numeric_answer_computes_percentage_change():
    answer = finance_numeric_answer(
        "What was the percentage change in revenue from 2021 to 2022?",
        [
            {
                "evidence_id": "revenue-table-cells",
                "text": (
                    "Revenue was $10.0 million in 2021. Revenue was "
                    "$12.5 million in 2022."
                ),
            }
        ],
    )

    assert answer is not None
    assert answer.answer == "25.0%"
    assert answer.question_type == "percentage_change"


def test_finance_numeric_answer_binds_operand_dimensions_from_cell_metadata():
    answer = finance_numeric_answer(
        "What was the percentage change in Example Corp revenue from 2021 to 2022?",
        [
            {
                "element_id": "cell-revenue-2021",
                "text": "Example Corp revenue was $10.0 million in 2021.",
                "metadata": {
                    "entity": "Example Corp",
                    "unit": "USD",
                    "scale": "million",
                    "currency": "USD",
                    "period": "2021",
                },
            },
            {
                "element_id": "cell-revenue-2022",
                "text": "Example Corp revenue was $12.5 million in 2022.",
                "metadata": {
                    "entity": "Example Corp",
                    "unit": "USD",
                    "scale": "million",
                    "currency": "USD",
                    "period": "2022",
                },
            },
        ],
    )

    assert answer is not None
    assert answer.answer == "25.0%"
    operands = {
        operand["operand_id"]: operand
        for operand in answer.calculation_plan["operands"]
    }
    assert operands["prior"] == {
        "operand_id": "prior",
        "input_id": "prior",
        "evidence_id": "cell-revenue-2021",
        "evidence_identity": "element::cell-revenue-2021",
        "value": "10.0",
        "unit": "USD",
        "scale": "million",
        "currency": "USD",
        "period": "2021",
        "entity": "Example Corp",
        "source": "evidence",
        "dimension_evidence_id": "cell-revenue-2021",
        "dimension_evidence_identity": "element::cell-revenue-2021",
        "dimension_binding_scope": "table",
        "scale_evidence_id": "cell-revenue-2021",
        "scale_evidence_identity": "element::cell-revenue-2021",
    }
    assert operands["current"]["evidence_id"] == "cell-revenue-2022"
    assert operands["current"]["entity"] == "Example Corp"
    assert answer.calculation_verification["valid"] is True
    assert answer.calculation_execution["citation_ids"] == [
        "element::cell-revenue-2021",
        "element::cell-revenue-2022",
    ]


def test_finance_numeric_answer_does_not_reuse_one_cell_for_equal_operands():
    answer = finance_numeric_answer(
        "What was the current ratio in 2022?",
        [
            {
                "element_id": "current-assets",
                "text": "Current assets were $100 million in 2022.",
            },
            {
                "element_id": "current-liabilities",
                "text": "Current liabilities were $100 million in 2022.",
            },
        ],
    )

    assert answer is not None
    assert answer.calculation_verification["valid"] is True
    assert answer.calculation_execution["citation_ids"] == [
        "element::current-assets",
        "element::current-liabilities",
    ]


def test_finance_numeric_answer_parses_negative_parentheses_for_difference():
    answer = finance_numeric_answer(
        "What was the difference in operating income from 2021 to 2022?",
        [
            {
                "evidence_id": "operating-income-cells",
                "text": (
                    "Operating income was $(120) million in 2021. "
                    "Operating income was $80 million in 2022."
                ),
            }
        ],
    )

    assert answer is not None
    assert answer.answer == "$200.0 million"
    assert answer.inputs["prior"] == -120.0


def test_finance_numeric_answer_does_not_emit_untraceable_guess():
    answer = finance_numeric_answer(
        "What was the percentage change in revenue from 2021 to 2022?",
        [{"text": "Revenue was 10 in 2021. Revenue was 12 in 2022."}],
    )

    assert answer is not None
    assert answer.answer == ""
    assert answer.confidence == 0.0
    assert not answer.calculation_verification["valid"]


def test_finance_route_blocks_llm_fallback_after_calculation_verification_failure():
    bundle = SimpleNamespace(
        items=[{"text": "Revenue was 10 in 2021. Revenue was 12 in 2022."}],
        metadata={},
    )

    answer = route_finance_numeric_answer(
        SimpleNamespace(
            prompt="What was the percentage change in revenue from 2021 to 2022?",
            verification_domain="finance",
        ),
        SimpleNamespace(route="hybrid_rag"),
        bundle,
    )

    assert answer == ""
    assert bundle.metadata["generation_backend"] == (
        "finance_calculation_verification_failed"
    )
    assert not bundle.metadata["finance_numeric_trace"]["calculation_verification"][
        "valid"
    ]


def test_finance_numeric_answer_does_not_execute_causal_percent_question():
    answer = finance_numeric_answer(
        (
            "What drove the reduction in SG&A expense as a percent of net "
            "sales in FY2023?"
        ),
        [
            {
                "evidence_id": "sga-table",
                "text": "SG&A expense was 37.6 percent of net sales in FY2023.",
            }
        ],
    )

    assert answer is None


def test_finance_numeric_answer_computes_three_period_average():
    answer = finance_numeric_answer(
        "What was the average adjusted EBITDA from 2020 through 2022?",
        [
            {
                "element_id": "ebitda-2020",
                "text": "Adjusted EBITDA was $100 million in 2020.",
            },
            {
                "element_id": "ebitda-2021",
                "text": "Adjusted EBITDA was $120 million in 2021.",
            },
            {
                "element_id": "ebitda-2022",
                "text": "Adjusted EBITDA was $140 million in 2022.",
            },
        ],
    )

    assert answer is not None
    assert answer.answer == "$120.0 million"
    assert answer.question_type == "multi_period_average"
    assert answer.calculation_verification["valid"] is True
    assert answer.calculation_execution["citation_ids"] == [
        "element::ebitda-2020",
        "element::ebitda-2021",
        "element::ebitda-2022",
    ]


def test_finance_numeric_answer_computes_multi_period_percentage_of_revenue():
    answer = finance_numeric_answer(
        (
            "What was the three year average of cost of goods sold as a % of "
            "revenue from FY2016 to FY2018?"
        ),
        [
            {
                "element_id": "cogs-revenue-2016",
                "text": (
                    "In 2016, cost of goods sold was $55 million and revenue "
                    "was $100 million."
                ),
            },
            {
                "element_id": "cogs-revenue-2017",
                "text": (
                    "In 2017, cost of goods sold was $60 million and revenue "
                    "was $100 million."
                ),
            },
            {
                "element_id": "cogs-revenue-2018",
                "text": (
                    "In 2018, cost of goods sold was $66 million and revenue "
                    "was $100 million."
                ),
            },
        ],
    )

    assert answer is not None
    assert answer.answer == "60.3%"
    assert answer.question_type == "multi_period_ratio_average"
    assert answer.calculation_verification["valid"] is True
    assert len(answer.calculation_plan["operands"]) == 6


def test_finance_numeric_answer_rejects_plan_missing_required_period_slot():
    answer = finance_numeric_answer(
        "What was the average adjusted EBITDA from 2020 through 2022?",
        [
            {
                "element_id": "ebitda-2020",
                "text": "Adjusted EBITDA was $100 million in 2020.",
            },
            {
                "element_id": "ebitda-2021",
                "text": "Adjusted EBITDA was $120 million in 2021.",
            },
        ],
        query_plan={
            "evidence_slots": [
                {
                    "slot_id": "operand:adjusted_ebitda:2020",
                    "role": "operand",
                    "metric": "adjusted ebitda",
                    "period": "2020",
                    "required": True,
                    "status": "filled",
                    "evidence_ids": ["ebitda-2020"],
                },
                {
                    "slot_id": "operand:adjusted_ebitda:2021",
                    "role": "operand",
                    "metric": "adjusted ebitda",
                    "period": "2021",
                    "required": True,
                    "status": "filled",
                    "evidence_ids": ["ebitda-2021"],
                },
                {
                    "slot_id": "operand:adjusted_ebitda:2022",
                    "role": "operand",
                    "metric": "adjusted ebitda",
                    "period": "2022",
                    "required": True,
                    "status": "missing",
                    "evidence_ids": [],
                },
            ]
        },
    )

    assert answer is not None
    assert answer.answer == ""
    assert answer.attempt_status == "verification_failed"
    assert "required_slot_missing:operand:adjusted_ebitda:2022" in (
        answer.calculation_verification["errors"]
    )


def test_finance_numeric_answer_computes_free_cash_flow():
    answer = finance_numeric_answer(
        "What was free cash flow in 2022?",
        [
            {
                "element_id": "operating-cash-flow",
                "text": (
                    "Net cash provided by operating activities was "
                    "$10 million in 2022."
                ),
            },
            {
                "element_id": "capital-expenditure",
                "text": "Capital expenditures were $4 million in 2022.",
            },
        ],
    )

    assert answer is not None
    assert answer.answer == "$6.0 million"
    assert answer.question_type == "free_cash_flow"
    assert answer.calculation_verification["valid"] is True


def test_finance_numeric_answer_executes_direct_capex_from_horizontal_cash_flow_row():
    answer = finance_numeric_answer(
        (
            "What is the FY2021 capital expenditure amount in USD billions "
            "for PepsiCo?"
        ),
        [
            {
                "element_id": "pepsico-page-63",
                "page_label": "63",
                "text": (
                    "Consolidated Statement of Cash Flows (in millions) "
                    "2021 2020 2019. Investing Activities. "
                    "Capital spending (4,625) (4,240) (4,232)."
                ),
            }
        ],
    )

    assert answer is not None
    assert answer.answer == "$4.6 billion"
    assert answer.question_type == "capital_expenditure"
    assert answer.calculation_verification["valid"] is True
    assert answer.calculation_execution["citation_ids"] == ["element::pepsico-page-63"]


def test_finance_numeric_answer_rejects_target_scale_inferred_from_unrelated_text():
    answer = finance_numeric_answer(
        "What is the FY2021 capital expenditure amount in USD billions?",
        [
            {
                "element_id": "pepsico-page-53",
                "text": (
                    "Debt issuances were $4.1 billion. "
                    "2021 2020 Change. Net cash provided by operating "
                    "activities $11,616 $10,613. Capital spending "
                    "(4,625) (4,240)."
                ),
            }
        ],
    )

    assert answer is not None
    assert answer.answer == ""
    assert answer.attempt_status == "verification_failed"
    assert (
        "operand_scale_missing_for_conversion:capital_expenditure_2021"
        in answer.calculation_verification["errors"]
    )


def test_finance_numeric_answer_supports_direct_current_assets():
    answer = finance_numeric_answer(
        "How much total current assets did Nike have at the end of FY2019?",
        [
            {
                "element_id": "nike-balance-sheet",
                "text": (
                    "Consolidated Balance Sheets (in millions). "
                    "2019 2018. Total current assets 16,525 15,134."
                ),
            }
        ],
    )

    assert answer is not None
    assert answer.answer == "$16,525 million"
    assert answer.question_type == "current_assets"
    assert answer.calculation_verification["valid"] is True


def test_finance_numeric_answer_supports_direct_net_ppe_with_serial_comma():
    answer = finance_numeric_answer(
        (
            "What is Boeing's year end FY2018 net property, plant, and "
            "equipment in USD millions?"
        ),
        [
            {
                "element_id": "boeing-balance-sheet",
                "text": (
                    "Consolidated Statements (in millions). 2018 2017. "
                    "Property, plant and equipment, net 12,645 12,211."
                ),
            }
        ],
    )

    assert answer is not None
    assert answer.answer == "$12,645 million"
    assert answer.question_type == "property_plant_equipment"
    assert answer.calculation_verification["valid"] is True


def test_finance_working_capital_operands_inherit_single_question_period():
    answer = finance_numeric_answer(
        (
            "What is FY2021 net working capital, defined as total current "
            "assets less total current liabilities? Answer in USD millions."
        ),
        [
            {
                "element_id": "balance-sheet-2021",
                "text": (
                    "Balance sheet (in millions)\n"
                    "2021 2020\n"
                    "Total current assets 19,815 19,378\n"
                    "Total current liabilities 13,997 13,933\n"
                    "An unrelated note describes a $3 billion debt capacity."
                ),
            }
        ],
        query_plan={
            "evidence_slots": [
                {
                    "slot_id": "operand:current_assets",
                    "role": "operand",
                    "metric": "current assets",
                    "period": "2021",
                    "required": True,
                    "status": "filled",
                    "evidence_ids": ["balance-sheet-2021"],
                },
                {
                    "slot_id": "operand:current_liabilities",
                    "role": "operand",
                    "metric": "current liabilities",
                    "period": "2021",
                    "required": True,
                    "status": "filled",
                    "evidence_ids": ["balance-sheet-2021"],
                },
            ]
        },
    )

    assert answer is not None
    assert answer.answer == "$5,818.0 million"
    assert answer.calculation_verification["valid"] is True
    assert {operand["period"] for operand in answer.calculation_plan["operands"]} == {
        "2021"
    }


def test_finance_numeric_answer_selects_requested_period_from_labeled_values():
    answer = finance_numeric_answer(
        "What is the FY2021 capital expenditure amount in USD millions?",
        [
            {
                "element_id": "cash-flow-row",
                "text": (
                    "Capital expenditures were $4,240 million in 2020. "
                    "Capital expenditures were $4,625 million in 2021."
                ),
            }
        ],
    )

    assert answer is not None
    assert answer.answer == "$4,625 million"
    assert answer.calculation_plan["operands"][0]["period"] == "2021"


def test_finance_numeric_answer_uses_average_inventory_for_turnover():
    answer = finance_numeric_answer(
        (
            "What was inventory turnover in 2022 using average inventory "
            "from 2021 and 2022?"
        ),
        [
            {
                "element_id": "cogs-2022",
                "text": "Cost of goods sold was $300 million in 2022.",
            },
            {
                "element_id": "inventory-2021",
                "text": "Inventory was $100 million in 2021.",
            },
            {
                "element_id": "inventory-2022",
                "text": "Inventory was $140 million in 2022.",
            },
        ],
    )

    assert answer is not None
    assert answer.answer == "2.5"
    assert answer.question_type == "inventory_turnover_average"
    assert answer.calculation_verification["valid"] is True


def test_finance_numeric_route_emits_failed_attempt_trace_for_unsupported_formula():
    bundle = SimpleNamespace(
        items=[
            {
                "element_id": "finance-cell",
                "text": "A finance table contains several reported values.",
            }
        ],
        metadata={
            "query_plan": {
                "answer_type": "numeric",
                "constraints": {"verification_domain": "finance"},
            }
        },
    )

    answer = route_finance_numeric_answer(
        SimpleNamespace(
            prompt="Calculate the compound annual growth rate for the portfolio.",
            verification_domain="finance",
        ),
        SimpleNamespace(route="hybrid_rag"),
        bundle,
    )

    assert answer == ""
    trace = bundle.metadata["finance_numeric_trace"]
    assert trace["attempt_status"] == "unsupported_formula"
    assert trace["calculation_verification"]["valid"] is False
    assert trace["calculation_verification"]["errors"] == ["unsupported_formula"]


def test_finance_numeric_trace_is_recorded_before_guarded_abstention():
    bundle = SimpleNamespace(items=[], metadata={})
    request = SimpleNamespace(
        controller_question=(
            "What is the FY2021 capital expenditure amount for PepsiCo?"
        ),
        verification_domain="finance",
    )

    ensure_finance_numeric_trace(request, bundle)

    trace = bundle.metadata["finance_numeric_trace"]
    assert trace["attempt_status"] == "missing_evidence"
    assert trace["calculation_execution"]["status"] == "error"
