from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ktem.docqa.evidence import _materialize_execution_cells
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan


def _finance_request(question: str) -> SimpleNamespace:
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


def test_real_page_credit_agreements_materialize_two_active_soft_wrapped_spans() -> None:
    question = (
        "As of May 26, 2023, what is the total amount PepsiCo may borrow under "
        "its unsecured revolving credit agreements?"
    )
    page = {
        "evidence_id": "pepsico-page-2",
        "source_id": "pepsico",
        "page_label": "2",
        "evidence_level": "page",
        "modality": "image",
        "text": (
            "Effective May 26, 2023, PepsiCo terminated the $3,800,000,000 364 "
            "day unsecured revolving credit agreement. On May 26, 2023, PepsiCo "
            "entered into a new $4,200,000,000 364 day unsecured revolving credit "
            "agreement (the 2023 364 Day Credit\nAgreement). The 2023 364 Day "
            "Credit\nAgreement enables PepsiCo to borrow up to $4,200,000,000. "
            "Effective May 26, 2023, PepsiCo terminated the $3,800,000,000 five "
            "year unsecured revolving credit agreement. On May 26, 2023, PepsiCo "
            "entered into a new $4,200,000,000 five year unsecured revolving "
            "credit agreement (the 2023 Five Year Credit\nAgreement). The 2023 "
            "Five Year Credit\nAgreement enables PepsiCo to borrow up to "
            "$4,200,000,000."
        ),
    }
    request = _finance_request(question)
    metadata: dict[str, Any] = {}

    expanded = _materialize_execution_cells(request, [page], metadata)
    spans = [item for item in expanded if item.get("evidence_level") == "span"]
    plan = bind_evidence_slots(request.query_plan, expanded)
    answer = finance_numeric_answer(question, expanded, query_plan=plan.as_dict())

    assert len(spans) == 4
    assert {
        (
            item["metadata"]["facility_type"],
            item["metadata"]["agreement_lifecycle_status"],
        )
        for item in spans
    } == {
        ("364_day", "terminated"),
        ("364_day", "active"),
        ("five_year", "terminated"),
        ("five_year", "active"),
    }
    assert answer is not None
    assert answer.answer == "$8,400,000,000"
    assert metadata["materialization_trace"]["materialized_cell_count"] == 4
    assert (
        metadata["materialization_trace"]["candidate_count_before_materialization"] == 1
    )
    assert (
        metadata["materialization_trace"]["candidate_count_after_materialization"] == 5
    )


def test_cash_flow_parent_identity_and_scale_beat_non_gaap_capital_spending() -> None:
    question = (
        "What is FY2021 capital expenditure in USD billions from the statement "
        "of cash flows?"
    )
    non_gaap = {
        "evidence_id": "non-gaap-parent",
        "source_id": "pepsico",
        "page_label": "53",
        "modality": "table",
        "statement_kind": "non_gaap_performance",
        "financial_scope": "consolidated",
        "text": (
            "Free cash flow is a non-GAAP financial measure.\n2021 2020\n"
            "Capital spending (4,625) (4,240)"
        ),
    }
    cash_flow = {
        "evidence_id": "cash-flow-parent",
        "source_id": "pepsico",
        "page_label": "63",
        "evidence_level": "page",
        "modality": "image",
        "text": (
            "Consolidated Statement of Cash Flows\nPepsiCo, Inc. and Subsidiaries\n"
            "Fiscal years ended December 25, 2021, December 26, 2020 and "
            "December 28, 2019\n(in millions)\n2021 2020 2019\n"
            "Capital spending (4,625) (4,240) (4,232)"
        ),
    }
    request = _finance_request(question)
    expanded = _materialize_execution_cells(request, [non_gaap, cash_flow], {})
    plan = bind_evidence_slots(request.query_plan, expanded)
    answer = finance_numeric_answer(question, expanded, query_plan=plan.as_dict())

    [operand_slot] = [slot for slot in plan.evidence_slots if slot.role == "operand"]
    assert "page%3A63" in operand_slot.evidence_ids[0]
    assert answer is not None
    assert answer.answer == "$4.6 billion"
    assert answer.calculation_plan["operands"][0]["scale"] == "million"
    assert (
        "cash-flow-parent"
        in answer.calculation_plan["operands"][0]["scale_evidence_identity"]
    )


def test_real_income_and_balance_pages_execute_inventory_turnover() -> None:
    question = (
        "What is FY2019 inventory turnover using FY2019 COGS divided by "
        "average inventory between FY2018 and FY2019?"
    )
    pages = [
        {
            "evidence_id": "income-page-50",
            "source_id": "kraft",
            "page_label": "50",
            "evidence_level": "page",
            "modality": "image",
            "text": (
                "Consolidated Statements of Income\n(in millions)\n2019 2018\n"
                "Net sales 26,185 26,259\nCost of products sold 16,830 16,500"
            ),
        },
        {
            "evidence_id": "balance-page-114",
            "source_id": "kraft",
            "page_label": "114",
            "evidence_level": "page",
            "modality": "image",
            "text": (
                "Consolidated Balance Sheets\n(in millions)\n2019 2018\n"
                "Inventories 2,721 2,667"
            ),
        },
    ]
    request = _finance_request(question)
    expanded = _materialize_execution_cells(request, pages, {})
    plan = bind_evidence_slots(request.query_plan, expanded)
    answer = finance_numeric_answer(question, expanded, query_plan=plan.as_dict())

    assert answer is not None
    assert answer.answer == "6.25"
    assert answer.calculation_execution["status"] == "ok"
    assert any(
        operand["row_label"] == "Cost of products sold"
        and float(operand["value"]) == 16830
        for operand in answer.calculation_plan["operands"]
    )


def test_real_balance_page_executes_total_current_assets() -> None:
    question = (
        "How much total current assets were reported at the end of FY2019 in "
        "USD millions?"
    )
    page = {
        "evidence_id": "nike-balance-page-54",
        "source_id": "nike",
        "page_label": "54",
        "evidence_level": "page",
        "modality": "image",
        "text": (
            "Consolidated Balance Sheets\n(in millions)\n2019 2018\n"
            "Cash and equivalents 4,466 3,955\n"
            "Total current assets 16,525 15,134"
        ),
    }
    request = _finance_request(question)
    expanded = _materialize_execution_cells(request, [page], {})
    plan = bind_evidence_slots(request.query_plan, expanded)
    answer = finance_numeric_answer(question, expanded, query_plan=plan.as_dict())

    assert answer is not None
    assert answer.answer == "$16,525 million"
    assert answer.calculation_plan["operands"][0]["statement_kind"] == ("balance_sheet")
