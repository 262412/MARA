from ktem.docqa.finance_numeric_answer import finance_numeric_answer


def test_finance_free_cash_flow_rebinds_unresolved_slots_to_atomic_evidence():
    answer = finance_numeric_answer(
        "What was free cash flow in 2020?",
        [
            {
                "evidence_id": "operating-cash-flow-2020",
                "cell_id": "operating-cash-flow-2020",
                "evidence_level": "cell",
                "cell_role": "data",
                "row_label": "Net cash provided by operating activities",
                "column_label": "2020",
                "period": "2020",
                "value": "3676.2",
                "scale": "million",
                "statement_kind": "cash_flow_statement",
                "financial_scope": "consolidated",
                "text": (
                    "Cash flow statement. Net cash provided by operating "
                    "activities 2020 3,676.2 million."
                ),
            },
            {
                "evidence_id": "capital-expenditure-2020",
                "cell_id": "capital-expenditure-2020",
                "evidence_level": "cell",
                "cell_role": "data",
                "row_label": "Capital expenditures",
                "column_label": "2020",
                "period": "2020",
                "value": "460.8",
                "scale": "million",
                "statement_kind": "cash_flow_statement",
                "financial_scope": "consolidated",
                "text": (
                    "Cash flow statement. Capital expenditures 2020 " "460.8 million."
                ),
            },
        ],
        query_plan={
            "evidence_slots": [
                {
                    "slot_id": "operand:operating_cash_flow:2020",
                    "role": "operand",
                    "metric": "operating cash flow",
                    "period": "2020",
                    "required": True,
                    "status": "filled",
                    "evidence_ids": ["cash-flow-2020"],
                },
                {
                    "slot_id": "operand:capital_expenditure:2020",
                    "role": "operand",
                    "metric": "capital expenditure",
                    "period": "2020",
                    "required": True,
                    "status": "filled",
                    "evidence_ids": ["cash-flow-2020"],
                },
            ]
        },
    )

    assert answer is not None
    assert answer.answer == "$3,215.4 million"
    assert answer.attempt_status == "executed"
    assert answer.calculation_verification["valid"] is True
    assert {
        trace["replacement_reason"]
        for trace in answer.authoritative_query_plan["binding_trace"]
    } == {"unresolved_existing_identity"}
    assert answer.calculation_verification["citation_ids"] == (
        "cell::operating-cash-flow-2020",
        "cell::capital-expenditure-2020",
    )


def test_finance_numeric_answer_sums_active_revolving_credit_agreements():
    answer = finance_numeric_answer(
        (
            "As of May 26, 2023, what is the total amount Pepsico may borrow "
            "under its unsecured revolving credit agreements?"
        ),
        [
            {
                "element_id": "pepsico-credit-agreements",
                "text": (
                    "On May 26, 2023, PepsiCo entered into a new "
                    "$4,200,000,000 364 day unsecured revolving credit "
                    "agreement. The agreement enables PepsiCo to borrow up to "
                    "$4,200,000,000. On May 26, 2023, PepsiCo entered into a "
                    "new $4,200,000,000 five year unsecured revolving credit "
                    "agreement. The agreement enables PepsiCo to borrow up to "
                    "$4,200,000,000."
                ),
            }
        ],
    )

    assert answer is not None
    assert answer.answer == "$8,400,000,000"
    assert answer.inputs == {
        "revolving_credit_capacity_1": 4_200_000_000.0,
        "revolving_credit_capacity_2": 4_200_000_000.0,
    }
    assert answer.calculation_verification["valid"] is True
