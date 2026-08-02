from __future__ import annotations

from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.finance_calculation_adapter import finance_calculation_audit
from ktem.docqa.finance_formula_inputs import formula_input_specs
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan

from .test_docqa_execution_slot_lineage_contract import _cell


def test_direct_value_uses_metric_input_id_and_exact_query_slot() -> None:
    question = "What were FY2021 net sales?"
    cell = {
        **_cell("sales", "Net sales", "100", period="2021"),
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
    }
    plan = bind_evidence_slots(
        build_query_plan(
            question, answer_type="numeric", verification_domain="finance"
        ),
        [cell],
    )
    specs = formula_input_specs(
        question_type="net_sales",
        input_ids=("net_sales_2021",),
        query_plan=plan.as_dict(),
    )

    assert specs[0].input_id == "net_sales_2021"
    assert specs[0].query_slot_id == "operand:net_sales:2021"
    assert specs[0].required_for_execution is True


def test_generic_value_input_is_rejected_when_query_slot_is_authoritative() -> None:
    question = "What were FY2021 net sales?"
    cell = {
        **_cell("sales", "Net sales", "100", period="2021"),
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
    }
    plan = bind_evidence_slots(
        build_query_plan(
            question, answer_type="numeric", verification_domain="finance"
        ),
        [cell],
    )

    audit = finance_calculation_audit(
        question,
        [cell],
        question_type="net_sales",
        inputs={"value": 100},
        query_plan=plan.as_dict(),
    )

    [operand] = audit.plan.operands
    assert operand.query_slot_id == ""
    assert operand.evidence_id == ""
    assert audit.verification.valid is False


def test_same_metric_operands_keep_distinct_input_and_slot_ids() -> None:
    question = "What was the percentage change in revenue from 2020 to 2021?"
    cells = [
        {
            **_cell("sales-2020", "Net sales", "90", period="2020"),
            "statement_kind": "income_statement",
            "financial_scope": "consolidated",
        },
        {
            **_cell("sales-2021", "Net sales", "100", period="2021"),
            "statement_kind": "income_statement",
            "financial_scope": "consolidated",
        },
    ]
    plan = bind_evidence_slots(
        build_query_plan(
            question, answer_type="numeric", verification_domain="finance"
        ),
        cells,
    )

    audit = finance_calculation_audit(
        question,
        cells,
        question_type="percentage_change",
        inputs={"revenue_2020": 90, "revenue_2021": 100},
        query_plan=plan.as_dict(),
    )

    operands = audit.plan.as_dict()["operands"]
    assert {operand["input_id"] for operand in operands} == {
        "revenue_2020",
        "revenue_2021",
    }
    assert {operand["query_slot_id"] for operand in operands} == {
        "operand:revenue:2020",
        "operand:revenue:2021",
    }
    assert all(operand["evidence_identity"] for operand in operands)


def test_collection_slot_cardinality_does_not_guess_aggregate_inputs() -> None:
    query_plan = {
        "evidence_slots": [
            {
                "slot_id": "operand:revolving_credit_capacity",
                "role": "operand",
                "metric": "revolving credit capacity",
                "required_for_execution": True,
                "cardinality": 2,
                "evidence_ids": ["span:report:first", "span:report:second"],
            }
        ]
    }
    specs = formula_input_specs(
        question_type="revolving_credit_capacity",
        input_ids=(
            "revolving_credit_capacity_1",
            "revolving_credit_capacity_2",
        ),
        query_plan=query_plan,
    )

    assert [spec.cardinality for spec in specs] == [2, 2]
    assert [spec.operator_role for spec in specs] == ["collection:1", "collection:2"]
    assert all(
        spec.query_slot_id == "operand:revolving_credit_capacity" for spec in specs
    )


def test_unstructured_aggregate_slot_does_not_bind_numbered_inputs() -> None:
    query_plan = {
        "evidence_slots": [
            {
                "slot_id": "operand:revolving_credit_capacity:2023",
                "role": "operand",
                "metric": "revolving credit capacity",
                "required_for_execution": True,
                "evidence_ids": ["span:report:first", "span:report:second"],
            }
        ]
    }

    specs = formula_input_specs(
        question_type="revolving_credit_capacity",
        input_ids=(
            "revolving_credit_capacity_1",
            "revolving_credit_capacity_2",
        ),
        query_plan=query_plan,
    )

    assert all(spec.query_slot_id == "" for spec in specs)


def test_revolving_total_query_plan_declares_collection_cardinality() -> None:
    plan = build_query_plan(
        (
            "As of May 26, 2023, what is the total amount the company may "
            "borrow under its revolving credit agreements?"
        ),
        answer_type="numeric",
        verification_domain="finance",
    )

    [slot] = [value for value in plan.evidence_slots if value.role == "operand"]
    assert slot.cardinality == 2
    assert slot.operator_role == "collection"


def test_revolving_collection_executes_two_ordered_evidence_identities() -> None:
    question = (
        "As of May 26, 2023, what is the total amount the company may "
        "borrow under its revolving credit agreements?"
    )
    cells = [
        _cell(
            "facility-364-day",
            "Revolving credit agreement may borrow",
            "4200000000",
            period="2023",
        ),
        _cell(
            "facility-five-year",
            "Revolving credit agreement may borrow",
            "4200000000",
            period="2023",
        ),
    ]
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        cells,
    )

    answer = finance_numeric_answer(
        question,
        cells,
        query_plan=plan.as_dict(),
    )

    assert answer is not None
    assert answer.answer == "$8,400,000,000"
    assert answer.calculation_verification["valid"] is True
    operands = answer.calculation_plan["operands"]
    assert len({operand["evidence_identity"] for operand in operands}) == 2
    assert all(
        operand["query_slot_id"] == "operand:revolving_credit_capacity:2023"
        for operand in operands
    )


def test_formula_input_and_operand_references_are_bidirectional() -> None:
    question = "What were FY2021 net sales?"
    cell = {
        **_cell("sales", "Net sales", "100", period="2021"),
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
    }
    plan = bind_evidence_slots(
        build_query_plan(
            question, answer_type="numeric", verification_domain="finance"
        ),
        [cell],
    )
    audit = finance_calculation_audit(
        question,
        [cell],
        question_type="net_sales",
        inputs={"net_sales_2021": 100},
        query_plan=plan.as_dict(),
    )
    payload = audit.plan.as_dict()

    [spec] = payload["formula_inputs"]
    [operand] = payload["operands"]
    assert spec["input_id"] == operand["input_id"]
    assert spec["query_slot_id"] == operand["query_slot_id"]
    assert operand["evidence_identity"] == identity_of(cell).key
