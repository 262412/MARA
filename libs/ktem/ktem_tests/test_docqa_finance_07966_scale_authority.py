from __future__ import annotations

from typing import Any

from ktem.docqa.calculation_evidence_identity import calculation_evidence_items
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.finance_numeric_answer import (
    finance_numeric_answer,
    reconcile_provisional_query_plan,
)
from ktem.docqa.finance_scale import source_scale_evidence
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan
from ktem.docqa.required_slot_selection import required_slot_shortlist

_SOURCE = "ACTIVISIONBLIZZARD_2019_10K"


def _cell(
    evidence_id: str,
    row_label: str,
    period: str,
    value: str,
    *,
    page_label: str,
    table_id: str,
    statement_kind: str,
    column_index: int,
    materialization_source_id: str,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": _SOURCE,
        "file_id": _SOURCE,
        "page_label": page_label,
        "table_id": table_id,
        "table_instance_id": table_id,
        "table_group_id": table_id,
        "block_id": table_id,
        "materialization_source_id": materialization_source_id,
        "parent_element_id": materialization_source_id,
        "evidence_level": "cell",
        "cell_role": "data",
        "cell_id": evidence_id,
        "row_index": 1,
        "column_index": column_index,
        "row_label": row_label,
        "column_label": period,
        "period": period,
        "value": value,
        "currency": "USD",
        "statement_kind": statement_kind,
        "financial_scope": "consolidated",
        "text": f"{row_label} {period} {value} USD",
    }


def _07966_page_level_scale_evidence() -> list[dict[str, Any]]:
    page30_convention = {
        "evidence_id": "page30-scale-convention",
        "canonical_id": "element:ACTIVISIONBLIZZARD_2019_10K:page30-scale-convention",
        "source_id": _SOURCE,
        "file_id": _SOURCE,
        "page_label": "30",
        "evidence_level": "page",
        "element_type": "page",
        "text": (
            "All amounts set forth in the following tables are in millions, "
            "except per share data."
        ),
    }
    income_parent = {
        "evidence_id": "income-table-page30",
        "element_id": "income-table-page30",
        "source_id": _SOURCE,
        "file_id": _SOURCE,
        "page_label": "30",
        "table_id": "income-table-page30",
        "table_instance_id": "income-table-page30",
        "table_group_id": "income-table-page30",
        "block_id": "income-table-page30",
        "evidence_level": "table",
        "element_type": "table",
        "text": "Consolidated Statements of Operations; Net revenues table",
    }
    cash_parent = {
        "evidence_id": "cash-table-page73",
        "element_id": "cash-table-page73",
        "source_id": _SOURCE,
        "file_id": _SOURCE,
        "page_label": "73",
        "table_id": "cash-table-page73",
        "table_instance_id": "cash-table-page73",
        "table_group_id": "cash-table-page73",
        "block_id": "cash-table-page73",
        "evidence_level": "table",
        "element_type": "table",
        "text": "Consolidated Statements of Cash Flows (Amounts in millions)",
    }
    evidence: list[dict[str, Any]] = [page30_convention, income_parent, cash_parent]
    for column_index, (period, capex, revenue) in enumerate(
        (("2017", "-155", "7017"), ("2018", "-131", "7500"), ("2019", "-116", "6489")),
        start=1,
    ):
        evidence.extend(
            (
                _cell(
                    f"capex-{period}",
                    "Capital expenditures",
                    period,
                    capex,
                    page_label="73",
                    table_id="cash-table-page73",
                    statement_kind="cash_flow_statement",
                    column_index=column_index,
                    materialization_source_id="cash-table-page73",
                ),
                _cell(
                    f"revenue-{period}",
                    "Net revenues",
                    period,
                    revenue,
                    page_label="30",
                    table_id="income-table-page30",
                    statement_kind="income_statement",
                    column_index=column_index,
                    materialization_source_id="income-table-page30",
                ),
            )
        )
    return evidence


def test_07966_page30_convention_provides_scale_for_each_revenue_operand() -> None:
    question = (
        "What is the FY2017 - FY2019 3 year average of capex as a % of "
        "revenue? Answer in units of percents and round to one decimal place."
    )
    evidence = _07966_page_level_scale_evidence()
    expanded = calculation_evidence_items(evidence)
    plan = bind_evidence_slots(
        build_query_plan(
            question, answer_type="numeric", verification_domain="finance"
        ),
        expanded,
    )

    answer = finance_numeric_answer(question, expanded, query_plan=plan.as_dict())

    assert answer is not None
    assert answer.answer == "1.9%"
    assert answer.calculation_verification["valid"] is True
    convention_identity = identity_of(evidence[0]).key
    operands = {
        operand["query_slot_id"]: operand
        for operand in answer.calculation_plan["operands"]
    }
    for period in ("2017", "2018", "2019"):
        operand = operands[f"operand:net_sales:{period}"]
        assert operand["scale"] == "million"
        assert operand["scale_evidence_identity"] == convention_identity
        assert operand["dimension_binding_scope"] == "page"
    for period in ("2017", "2018", "2019"):
        operand = operands[f"operand:capital_expenditure:{period}"]
        assert operand["scale"] == "million"
        assert operand["scale_evidence_identity"] == identity_of(evidence[2]).key
        assert operand["dimension_binding_scope"] == "table"
    dimension = next(
        slot
        for slot in answer.authoritative_query_plan["evidence_slots"]
        if slot["slot_id"] == "dimension:scale"
    )
    assert dimension["status"] == "filled"
    assert set(dimension["applied_query_slot_ids"]) == set(operands)
    assert set(dimension["evidence_ids"]) == {
        convention_identity,
        identity_of(evidence[2]).key,
    }


def test_07966_page30_convention_is_reserved_when_required_candidate_budget_is_full() -> (
    None
):
    question = (
        "What is the FY2017 - FY2019 3 year average of capex as a % of "
        "revenue? Answer in units of percents and round to one decimal place."
    )
    evidence = _07966_page_level_scale_evidence()
    plan = build_query_plan(
        question,
        answer_type="numeric",
        verification_domain="finance",
    )
    selected, _restored = required_slot_shortlist(
        evidence,
        plan,
        candidate_limit=8,
    )

    convention_identity = identity_of(evidence[0]).key
    selected_ids = {identity_of(item).key for item in selected}
    assert len(selected) == 8
    assert convention_identity in selected_ids
    assert identity_of(evidence[2]).key in selected_ids
    assert {
        identity_of(item).key
        for item in evidence
        if item.get("evidence_level") == "cell"
    } <= selected_ids


def test_partial_scale_dimension_cannot_become_authoritative() -> None:
    query_plan = {
        "evidence_slots": [
            {
                "slot_id": "operand:capital_expenditure:2017",
                "role": "operand",
                "required_for_execution": True,
            },
            {
                "slot_id": "operand:net_sales:2017",
                "role": "operand",
                "required_for_execution": True,
            },
            {
                "slot_id": "operand:capital_expenditure:2018",
                "role": "operand",
                "required_for_execution": True,
            },
            {
                "slot_id": "operand:net_sales:2018",
                "role": "operand",
                "required_for_execution": True,
            },
            {
                "slot_id": "dimension:scale",
                "role": "dimension",
                "required_for_execution": True,
            },
        ]
    }
    calculation_plan = {
        "operands": [
            {
                "operand_id": "capital_expenditure_2017",
                "query_slot_id": "operand:capital_expenditure:2017",
                "scale": "million",
                "scale_evidence_identity": "element:cash-flow",
                "dimension_binding_scope": "table",
            },
            {
                "operand_id": "net_sales_2017",
                "query_slot_id": "operand:net_sales:2017",
                "scale": "",
                "scale_evidence_identity": "",
                "dimension_binding_scope": "",
            },
            {
                "operand_id": "capital_expenditure_2018",
                "query_slot_id": "operand:capital_expenditure:2018",
                "scale": "million",
                "scale_evidence_identity": "element:cash-flow",
                "dimension_binding_scope": "table",
            },
            {
                "operand_id": "net_sales_2018",
                "query_slot_id": "operand:net_sales:2018",
                "scale": "",
                "scale_evidence_identity": "",
                "dimension_binding_scope": "",
            },
        ]
    }

    reconciled = reconcile_provisional_query_plan(
        query_plan,
        calculation_plan,
    )
    dimension = next(
        slot
        for slot in reconciled["evidence_slots"]
        if slot["slot_id"] == "dimension:scale"
    )

    assert dimension["status"] == "missing"
    assert dimension.get("scale", "") == ""
    assert dimension["applied_query_slot_ids"] == [
        "operand:capital_expenditure:2017",
        "operand:capital_expenditure:2018",
    ]


def test_page30_scale_convention_cannot_cross_bind_page73_cash_flow_cells() -> None:
    evidence = _07966_page_level_scale_evidence()
    capex = next(item for item in evidence if item.get("evidence_id") == "capex-2017")
    capex_parent = next(
        item for item in evidence if item.get("evidence_id") == "cash-table-page73"
    )
    capex_parent["text"] = "Consolidated Statements of Cash Flows"

    assert source_scale_evidence(capex, [evidence[0], capex_parent, capex]) == ("", "")


def test_scale_convention_rejects_a_different_source_even_on_the_same_page() -> None:
    evidence = _07966_page_level_scale_evidence()
    revenue = next(
        item for item in evidence if item.get("evidence_id") == "revenue-2017"
    )
    foreign_convention = {
        **evidence[0],
        "evidence_id": "foreign-scale-convention",
        "canonical_id": "element:OTHER_REPORT:foreign-scale-convention",
        "source_id": "OTHER_REPORT",
    }

    assert source_scale_evidence(revenue, [revenue, foreign_convention]) == ("", "")


def test_same_page_unrelated_table_scale_does_not_bind_to_revenue_cell() -> None:
    evidence = _07966_page_level_scale_evidence()
    revenue = next(
        item for item in evidence if item.get("evidence_id") == "revenue-2017"
    )
    unrelated_sibling = {
        "evidence_id": "page30-unrelated-sibling",
        "source_id": _SOURCE,
        "page_label": "30",
        "table_id": "unrelated-table-page30",
        "table_instance_id": "unrelated-table-page30",
        "table_group_id": "unrelated-table-page30",
        "evidence_level": "table",
        "element_type": "table",
        "text": "Unrelated table (Amounts in billions)",
    }

    assert source_scale_evidence(revenue, [revenue, unrelated_sibling]) == ("", "")


def test_conflicting_scale_headers_fail_closed_at_the_same_table_scope() -> None:
    evidence = _07966_page_level_scale_evidence()
    revenue = next(
        item for item in evidence if item.get("evidence_id") == "revenue-2017"
    )
    million_header = {
        "evidence_id": "income-million-header",
        "source_id": _SOURCE,
        "page_label": "30",
        "table_instance_id": "income-table-page30",
        "table_group_id": "income-table-page30",
        "evidence_level": "span",
        "text": "Consolidated statements of income (in millions)",
    }
    billion_header = {
        **million_header,
        "evidence_id": "income-billion-header",
        "text": "Consolidated statements of income (in billions)",
    }

    assert source_scale_evidence(
        revenue,
        [revenue, million_header, billion_header],
    ) == ("", "")


def test_scale_header_without_canonical_identity_is_not_authoritative() -> None:
    evidence = _07966_page_level_scale_evidence()
    revenue = next(
        item for item in evidence if item.get("evidence_id") == "revenue-2017"
    )
    missing_identity_header = {
        "source_id": _SOURCE,
        "page_label": "30",
        "table_instance_id": "income-table-page30",
        "table_group_id": "income-table-page30",
        "evidence_level": "span",
        "text": "Consolidated statements of income (in millions)",
    }

    assert source_scale_evidence(revenue, [revenue, missing_identity_header]) == (
        "",
        "",
    )
