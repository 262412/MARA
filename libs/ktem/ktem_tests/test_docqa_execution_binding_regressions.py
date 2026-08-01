from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_set_selection import select_evidence_for_plan
from ktem.docqa.execution_slot_lineage import linked_dimension_candidate
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan

from .test_docqa_execution_slot_lineage_contract import _cell


def test_binding_prefers_scale_backed_atomic_cell_over_unscoped_duplicate() -> None:
    question = "What was FY2018 net property, plant and equipment in USD millions?"
    plan = build_query_plan(
        question,
        answer_type="numeric",
        verification_domain="finance",
    )
    unscoped = {
        **_cell(
            "ppe-unscoped",
            "Property, plant and equipment, net",
            "12645",
            period="2018",
        ),
        "scale": "",
    }
    scoped = {
        **_cell(
            "ppe-scoped",
            "Property, plant and equipment, net",
            "12645",
            period="2018",
        ),
        "scale": "million",
        "text": "Property, plant and equipment, net 2018 12645 million USD",
    }

    bound = bind_evidence_slots(plan, [unscoped, scoped])
    [operand] = [slot for slot in bound.evidence_slots if slot.role == "operand"]

    assert operand.evidence_ids[0] == identity_of(scoped).key


def test_execution_uses_query_plan_selected_cell_not_unscoped_duplicate() -> None:
    question = "What was FY2018 net property, plant and equipment in USD millions?"
    unscoped = {
        **_cell(
            "ppe-unscoped",
            "Property, plant and equipment, net",
            "12645",
            period="2018",
        ),
        "scale": "",
        "materialization_source_id": "",
    }
    scoped = {
        **_cell(
            "ppe-scoped",
            "Property, plant and equipment, net",
            "12645",
            period="2018",
        ),
        "scale": "million",
        "materialization_source_id": "scale-parent",
        "text": "Property, plant and equipment, net 2018 12645 million USD",
    }
    parent = {
        "evidence_id": "scale-parent",
        "source_id": "report",
        "page_label": "12",
        "table_instance_id": "balance-sheet-block-1",
        "table_group_id": "balance-sheet",
        "element_type": "table",
        "modality": "table",
        "scale": "million",
        "text": "Consolidated balance sheets (in millions)",
    }
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        [unscoped, scoped, parent],
    )

    answer = finance_numeric_answer(
        question,
        [unscoped, scoped, parent],
        query_plan=plan.as_dict(),
    )

    assert answer is not None
    assert answer.answer == "$12,645 million"
    assert answer.calculation_execution["status"] == "ok"
    assert answer.calculation_plan["operands"][0]["evidence_id"] == "ppe-scoped"


def test_parenthesized_scale_header_binds_to_materialized_operand() -> None:
    question = "What was FY2018 capital expenditure in USD millions?"
    parent = {
        "evidence_id": "cash-flow-parent",
        "source_id": "report",
        "page_label": "60",
        "table_instance_id": "cash-flow-table",
        "table_group_id": "cash-flow",
        "element_type": "table",
        "modality": "table",
        "statement_kind": "cash_flow_statement",
        "financial_scope": "consolidated",
        "text": "CONSOLIDATED STATEMENTS OF CASH FLOWS\n(Millions)",
    }
    operand = {
        **_cell(
            "capex-2018",
            "Purchases of property, plant and equipment",
            "1577",
            period="2018",
        ),
        "statement_kind": "cash_flow_statement",
        "table_instance_id": "cash-flow-table",
        "table_group_id": "cash-flow",
        "materialization_source_id": "cash-flow-parent",
        "scale": "",
    }
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        [parent, operand],
    )

    [dimension] = [slot for slot in plan.evidence_slots if slot.role == "dimension"]
    answer = finance_numeric_answer(
        question,
        [parent, operand],
        query_plan=plan.as_dict(),
    )

    assert dimension.status == "filled"
    assert dimension.evidence_ids == (identity_of(parent).key,)
    assert answer is not None
    assert answer.answer == "$1,577 million"
    assert answer.calculation_execution["status"] == "ok"


def _ratio_cell(
    evidence_id: str,
    row_label: str,
    value: str,
    period: str,
    *,
    statement_kind: str,
    table_id: str,
    table_group_id: str,
    scale: str,
) -> dict[str, Any]:
    return {
        **_cell(evidence_id, row_label, value, period=period),
        "statement_kind": statement_kind,
        "table_instance_id": table_id,
        "table_group_id": table_group_id,
        "materialization_source_id": table_id,
        "scale": scale,
    }


def _multi_period_ratio_evidence() -> list[dict[str, Any]]:
    page = {
        "evidence_id": "selected-financial-data-page",
        "source_id": "report",
        "page_label": "30",
        "evidence_level": "page",
        "text": (
            "All amounts set forth in the following tables\nare in millions, "
            "except per share data or as otherwise indicated."
        ),
    }
    net_sales_parent = {
        "evidence_id": "net-sales-table",
        "source_id": "report",
        "page_label": "30",
        "table_instance_id": "net-sales-table",
        "table_group_id": "selected-financial-data",
        "element_type": "table",
        "modality": "table",
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
        "text": "Net revenues 2019 6489 2018 7500 2017 7017",
    }
    capex_parent = {
        "evidence_id": "capex-table",
        "source_id": "report",
        "page_label": "73",
        "table_instance_id": "capex-table",
        "table_group_id": "cash-flow",
        "element_type": "table",
        "modality": "table",
        "statement_kind": "cash_flow_statement",
        "financial_scope": "consolidated",
        "scale": "million",
        "text": "Cash flows (in millions)",
    }
    evidence = [page, net_sales_parent, capex_parent]
    for period, capex, sales in (
        ("2017", "-155", "7017"),
        ("2018", "-131", "7500"),
        ("2019", "-116", "6489"),
    ):
        evidence.extend(
            [
                _ratio_cell(
                    f"capex-{period}",
                    "Capital expenditures",
                    capex,
                    period,
                    statement_kind="cash_flow_statement",
                    table_id="capex-table",
                    table_group_id="cash-flow",
                    scale="million",
                ),
                _ratio_cell(
                    f"net-sales-{period}",
                    "Net revenues",
                    sales,
                    period,
                    statement_kind="income_statement",
                    table_id="net-sales-table",
                    table_group_id="selected-financial-data",
                    scale="",
                ),
            ]
        )
    return evidence


def test_explicit_following_tables_scale_applies_to_same_page_table_cells() -> None:
    question = (
        "What is the FY2017 - FY2019 3 year average of capex as a % of "
        "revenue? Answer in units of percents and round to one decimal place."
    )
    evidence = _multi_period_ratio_evidence()
    net_sales_cell = next(
        item for item in evidence if item.get("evidence_id") == "net-sales-2017"
    )
    assert linked_dimension_candidate(net_sales_cell, evidence) == evidence[0]
    distractors = [
        {
            "evidence_id": f"distractor-{index}",
            "source_id": "report",
            "page_label": "30",
            "text": f"capex revenue average percentage discussion {index}",
        }
        for index in range(40)
    ]
    plan = build_query_plan(
        question,
        answer_type="numeric",
        verification_domain="finance",
    )
    selected, _trace, bound = select_evidence_for_plan(
        question,
        [*evidence[1:], *distractors, evidence[0]],
        plan,
    )

    answer = finance_numeric_answer(
        question,
        selected,
        query_plan=bound.as_dict(),
    )

    assert "selected-financial-data-page" in {item["evidence_id"] for item in selected}
    assert answer is not None
    assert answer.answer == "1.9%"
    assert answer.calculation_execution["status"] == "ok"
    net_sales_operands = [
        operand
        for operand in answer.calculation_plan["operands"]
        if operand["operand_id"].startswith("net_sales")
    ]
    assert {operand["scale"] for operand in net_sales_operands} == {"million"}
    assert {operand["scale_evidence_id"] for operand in net_sales_operands} == {
        "selected-financial-data-page"
    }
