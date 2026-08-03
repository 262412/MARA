from __future__ import annotations

from ktem.docqa.calculation_claim_verification import calculation_claim_result
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
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
    assert slot.entity == "active_at:2023-05-26"


def test_revolving_collection_excludes_terminated_facilities() -> None:
    question = (
        "As of May 26, 2023, what is the total amount the company may "
        "borrow under its revolving credit agreements?"
    )
    spans = [
        {
            **_cell(
                "terminated-364",
                "Revolving credit agreement may borrow",
                "3800000000",
                period="2023",
            ),
            "text": (
                "On May 26, 2023 the 364-day revolving agreement was terminated; "
                "it had allowed borrowing up to $3.8 billion."
            ),
        },
        {
            **_cell(
                "terminated-five-year",
                "Revolving credit agreement may borrow",
                "3800000000",
                period="2023",
            ),
            "text": (
                "On May 26, 2023 the five-year revolving agreement was terminated; "
                "it had allowed borrowing up to $3.8 billion."
            ),
        },
        {
            **_cell(
                "active-364",
                "Revolving credit agreement may borrow",
                "4200000000",
                period="2023",
            ),
            "text": (
                "On May 26, 2023 the company entered a new 364-day revolving "
                "agreement enabling borrowing up to $4.2 billion."
            ),
        },
        {
            **_cell(
                "active-five-year",
                "Revolving credit agreement may borrow",
                "4200000000",
                period="2023",
            ),
            "text": (
                "On May 26, 2023 the company entered a new five-year revolving "
                "agreement enabling borrowing up to $4.2 billion."
            ),
        },
    ]
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        spans,
    )

    [slot] = [value for value in plan.evidence_slots if value.role == "operand"]
    assert slot.evidence_ids == (
        identity_of(spans[2]).key,
        identity_of(spans[3]).key,
    )

    answer = finance_numeric_answer(question, spans, query_plan=plan.as_dict())

    assert answer is not None
    assert answer.answer == "$8,400,000,000"
    assert answer.calculation_execution["status"] == "ok"


def test_revolving_collection_executes_two_ordered_evidence_identities() -> None:
    question = (
        "As of May 26, 2023, what is the total amount the company may "
        "borrow under its revolving credit agreements?"
    )
    cells = [
        {
            **_cell(
                "facility-364-day",
                "Revolving credit agreement may borrow",
                "4200000000",
                period="2023",
            ),
            "text": (
                "On May 26, 2023 the company entered a new 364-day revolving "
                "agreement enabling borrowing up to $4.2 billion."
            ),
        },
        {
            **_cell(
                "facility-five-year",
                "Revolving credit agreement may borrow",
                "4200000000",
                period="2023",
            ),
            "text": (
                "On May 26, 2023 the company entered a new five-year revolving "
                "agreement enabling borrowing up to $4.2 billion."
            ),
        },
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


def test_fiscal_quarter_comparison_binds_distinct_atomic_periods() -> None:
    question = (
        "Was there any drop in cash and cash equivalents between FY2023 "
        "and Q2 of FY2024?"
    )
    cells = [
        {
            **_cell(
                "cash-fy2023",
                "Cash and cash equivalents",
                "1874",
                period="2023",
            ),
            "period_kind": "fiscal_year",
        },
        {
            **_cell(
                "cash-q2-fy2024",
                "Cash and cash equivalents",
                "1093",
                period="2024",
            ),
            "period_kind": "quarter",
            "entity": "fiscal_quarter:q2",
        },
    ]
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="extractive",
            verification_domain="finance",
        ),
        cells,
    )
    operand_slots = [slot for slot in plan.evidence_slots if slot.role == "operand"]

    assert [(slot.period, slot.period_kind, slot.entity) for slot in operand_slots] == [
        ("2023", "fiscal_year", ""),
        ("2024", "quarter", "fiscal_quarter:q2"),
    ]
    assert [slot.evidence_ids for slot in operand_slots] == [
        (identity_of(cells[0]).key,),
        (identity_of(cells[1]).key,),
    ]

    answer = finance_numeric_answer(question, cells, query_plan=plan.as_dict())
    assert answer is not None
    assert answer.answer == "Yes, a 41.7% decrease"
    assert answer.calculation_execution["status"] == "ok"
    assert answer.calculation_execution["signed_value"].startswith("-41.675")
    assert answer.calculation_execution["direction"] == "decrease"
    assert answer.calculation_execution["magnitude"].startswith("41.675")
    bundle = EvidenceBundle(
        route="doc_text",
        items=cells,
        metadata={"finance_numeric_trace": answer.as_trace()},
    )
    verification = calculation_claim_result(
        bundle,
        answer.answer,
        [answer.answer],
        domain="finance",
        prompt=question,
    )

    assert verification is not None
    assert verification.status == "supported"
    assert verification.contradicting_evidence_ids == ()


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
