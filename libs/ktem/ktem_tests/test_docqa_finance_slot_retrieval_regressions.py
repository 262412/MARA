from __future__ import annotations

from types import SimpleNamespace

import pytest
from ktem.docqa.evidence import build_evidence_bundle
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.query_planning import (
    bind_evidence_slots,
    build_query_plan,
    missing_slot_requests,
)
from ktem.reasoning import mara_route_retrieval
from ktem.reasoning.mara import MaraAgentPipeline


def _request(question: str) -> SimpleNamespace:
    return SimpleNamespace(
        prompt=question,
        answer_type="numeric",
        verification_domain="finance",
        query_plan=build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
    )


def test_revolving_capacity_slot_query_contains_agreement_synonyms_and_year():
    plan = build_query_plan(
        "As of May 26, 2023, what is the total amount Pepsico may borrow under "
        "its unsecured revolving credit agreements?",
        answer_type="numeric",
        verification_domain="finance",
    )

    [slot] = plan.evidence_slots
    query = slot.query.lower()
    assert "2023" in query
    assert "revolving credit agreement" in query
    assert "borrow up to" in query


def test_revolving_credit_text_route_binds_both_active_capacity_atoms():
    question = (
        "As of May 26, 2023, what is the total amount PepsiCo may borrow under "
        "its unsecured revolving credit agreements?"
    )
    page = {
        "evidence_id": "credit-agreements-page",
        "source_id": "pepsico-report",
        "evidence_level": "page",
        "modality": "text",
        "text": (
            "On May 26, 2023, PepsiCo entered into a new $4,200,000,000 "
            "364 day unsecured revolving credit agreement. The 2023 364 Day "
            "Credit Agreement enables PepsiCo to borrow up to $4,200,000,000. "
            "On May 26, 2023, PepsiCo entered into a new $4,200,000,000 five "
            "year unsecured revolving credit agreement. The 2023 Five Year "
            "Credit Agreement enables PepsiCo to borrow up to $4,200,000,000."
        ),
    }
    request = _request(question)

    bundle = build_evidence_bundle("text_rag", request, {"evidence": [page]})
    bound_plan = bind_evidence_slots(request.query_plan, bundle.items)
    answer = finance_numeric_answer(
        question,
        bundle.items,
        query_plan=bound_plan.as_dict(),
    )

    assert answer is not None
    assert answer.answer == "$8,400,000,000"
    [operand] = [slot for slot in bound_plan.evidence_slots if slot.role == "operand"]
    assert operand.status == "filled"
    assert len(operand.evidence_ids) == 2


def test_free_cash_flow_slot_queries_include_statement_row_synonyms():
    plan = build_query_plan(
        "According to the information provided in the statement of cash flows, "
        "what is the FY2020 free cash flow (FCF) for General Mills? FCF here is "
        "defined as: (cash from operations - capex). Answer in USD millions.",
        answer_type="numeric",
        verification_domain="finance",
    )

    queries = {
        slot.metric: slot.query.lower()
        for slot in plan.evidence_slots
        if slot.role == "operand"
    }
    assert "net cash provided by operating activities" in queries["operating cash flow"]
    assert "purchases of land buildings and equipment" in queries["capital expenditure"]
    assert all("2020" in query and "cash flows" in query for query in queries.values())
    dimension_query = next(
        slot.query.lower()
        for slot in plan.evidence_slots
        if slot.slot_id == "dimension:scale"
    )
    assert "2020" in dimension_query
    assert "cash flows" in dimension_query
    dimension_round2 = next(
        item["query"]
        for item in missing_slot_requests(plan)
        if item["slot_id"] == "dimension:scale"
    )
    assert "statement locator" in dimension_round2


def test_dimension_slot_query_keeps_operand_period_metric_and_statement_context():
    plan = build_query_plan(
        "What was FY2021 capital expenditure from the statement of cash flows "
        "in USD billions?",
        answer_type="numeric",
        verification_domain="finance",
    )

    dimension_query = next(
        slot.query.lower()
        for slot in plan.evidence_slots
        if slot.slot_id == "dimension:scale"
    )

    assert "2021" in dimension_query
    assert "capital expenditure" in dimension_query
    assert "cash flow" in dimension_query


def test_inventory_turnover_text_route_binds_each_year_and_statement_atom():
    question = (
        "What is FY2019 inventory turnover using FY2019 COGS divided by "
        "average inventory between FY2018 and FY2019?"
    )
    evidence = [
        {
            "evidence_id": "income-statement-page",
            "source_id": "report",
            "evidence_level": "page",
            "modality": "text",
            "text": (
                "Consolidated Statements of Income\n(in millions)\n2019 2018\n"
                "Cost of products sold 16,830 16,500"
            ),
        },
        {
            "evidence_id": "balance-sheet-page",
            "source_id": "report",
            "evidence_level": "page",
            "modality": "text",
            "text": (
                "Consolidated Balance Sheets\n(in millions)\n2019 2018\n"
                "Inventories 2,721 2,667"
            ),
        },
    ]
    request = _request(question)

    bundle = build_evidence_bundle("text_rag", request, {"evidence": evidence})
    bound_plan = bind_evidence_slots(request.query_plan, bundle.items)
    answer = finance_numeric_answer(
        question,
        bundle.items,
        query_plan=bound_plan.as_dict(),
    )

    assert answer is not None
    assert answer.answer == "6.25"
    required = [
        slot for slot in bound_plan.evidence_slots if slot.required_for_execution
    ]
    assert all(slot.status == "filled" for slot in required)
    assert {(slot.metric, slot.period) for slot in required} == {
        ("cost of goods sold", "2019"),
        ("inventory", "2018"),
        ("inventory", "2019"),
    }


@pytest.mark.parametrize("route", ("text_rag", "controller_auto", "crag_guarded"))
def test_finance_04854_materializes_cash_flow_slots_for_each_quality_route(route):
    question = (
        "According to the information provided in the statement of cash flows, "
        "what is the FY2020 free cash flow (FCF) for General Mills? FCF here is "
        "defined as: (cash from operations - capex). Answer in USD millions."
    )
    page = {
        "evidence_id": "general-mills-page-52",
        "source_id": "GENERALMILLS_2020_10K",
        "page_label": "52",
        "evidence_level": "page",
        "modality": "image",
        "text": (
            "Consolidated Statements of Cash Flows\n"
            "(In millions) 2020 2019\n"
            "Net cash provided by operating activities 3,676.2 3,100.0\n"
            "Purchases of land, buildings, and equipment (460.8) (400.0)"
        ),
    }
    request = _request(question)

    bundle = build_evidence_bundle(route, request, {"evidence": [page]})
    bound_plan = bind_evidence_slots(request.query_plan, bundle.items)
    answer = finance_numeric_answer(
        question,
        bundle.items,
        query_plan=bound_plan.as_dict(),
    )

    assert answer is not None
    assert answer.answer == "$3,215.4 million"
    assert {
        slot.metric
        for slot in bound_plan.evidence_slots
        if slot.required_for_execution and slot.role == "operand"
    } == {"operating cash flow", "capital expenditure"}
    assert all(
        slot.status == "filled"
        for slot in bound_plan.evidence_slots
        if slot.required_for_execution
    )
    assert all(
        item.get("evidence_level") == "cell"
        for item in bundle.items
        if item.get("evidence_level") in {"cell", "span"}
    )


def test_finance_element_route_uses_transient_required_slot_request():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.docqa_request = SimpleNamespace(
        answer_type="numeric",
        verification_domain="finance",
        retrieval_slot_id="",
    )
    pipeline.element_index_records = [
        {
            "evidence_id": "net-sales-2019",
            "file_id": "report",
            "page_label": "44",
            "element_id": "net-sales-2019",
            "element_type": "table",
            "modality": "table",
            "evidence_level": "cell",
            "table_id": "income-table",
            "cell_id": "net-sales-2019",
            "row_label": "Net sales",
            "column_label": "2019",
            "period": "2019",
            "value": "6489",
            "statement_kind": "income_statement",
            "financial_scope": "consolidated",
            "text": "Net sales 2019 6489",
        },
        {
            "evidence_id": "ppe-2019",
            "file_id": "report",
            "page_label": "45",
            "element_id": "ppe-2019",
            "element_type": "table",
            "modality": "table",
            "evidence_level": "cell",
            "table_id": "balance-table",
            "cell_id": "ppe-2019",
            "row_label": "Property, plant and equipment",
            "column_label": "2019",
            "period": "2019",
            "value": "253",
            "statement_kind": "balance_sheet",
            "financial_scope": "consolidated",
            "text": "Property, plant and equipment 2019 253",
        },
    ]
    request = SimpleNamespace(
        answer_type="numeric",
        verification_domain="finance",
        retrieval_slot_id="operand:net_sales:2019",
    )
    question = (
        "What is FY2019 fixed asset turnover using FY2019 revenue and "
        "average FY2018 and FY2019 property, plant and equipment?"
    )

    metadata = mara_route_retrieval.route_retrieval_metadata(
        pipeline,
        "element_rag",
        "net sales 2019",
        [],
        {"question": question, "modalities": ["table"]},
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("element route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
        request=request,
    )

    assert metadata["element_active_slot_id"] == "operand:net_sales:2019"
    assert metadata["element_active_slot_candidate_count"] >= 1
