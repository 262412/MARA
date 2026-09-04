from __future__ import annotations

from typing import Any

from ktem.docqa.calculation_evidence_identity import calculation_evidence_items
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan


def _operations_parent(
    evidence_id: str = "operations-image-parent",
    *,
    scale: str = "millions",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "report",
        "page_label": "70",
        "modality": "image",
        "evidence_level": "page",
        "text": (
            "CONSOLIDATED STATEMENTS OF OPERATIONS\n"
            f"(Amounts in {scale}, except per share data)\n"
            "For the Years Ended December 31,\n"
            "2019 2018 2017\n"
            "Product sales $ 1,975 2,255 2,110\n"
            "Subscription, licensing, and other revenues 4,514 5,245 4,907\n"
            "Total net revenues 6,489 7,500 7,017"
        ),
    }


def _revenue_child(**updates: Any) -> dict[str, Any]:
    evidence_id = (
        "source:report#page:70#table-instance:local-operations"
        "#block:block-1#row:3#column:1"
    )
    child = {
        "evidence_id": evidence_id,
        "cell_id": evidence_id,
        "source_id": "report",
        "page_label": "70",
        "modality": "table",
        "evidence_level": "cell",
        "cell_role": "data",
        "element_id": "local-operations",
        "parent_element_id": "local-operations",
        "materialization_source_id": "element:report:70:local-operations",
        "table_id": "local-operations",
        "table_instance_id": "local-operations",
        "table_group_id": "local-operations",
        "block_id": "block-1",
        "row_index": 3,
        "column_index": 1,
        "row_label": "Total net revenues",
        "column_label": "2019",
        "period": "2019",
        "period_kind": "fiscal_year",
        "value": "6489",
        "unit": "",
        "scale": "",
        "currency": "USD",
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
        "text": (
            "Total net revenues 2019 2019 fiscal_year 6489 USD "
            "income_statement consolidated data"
        ),
    }
    child.update(updates)
    return child


def _operand(
    evidence_id: str,
    row_label: str,
    value: str,
    period: str,
    *,
    statement_kind: str,
    table_id: str,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "canonical_id": f"cell:report:{evidence_id}",
        "cell_id": evidence_id,
        "source_id": "report",
        "page_label": "69",
        "evidence_level": "cell",
        "cell_role": "data",
        "row_label": row_label,
        "column_label": period,
        "period": period,
        "period_kind": "fiscal_year",
        "value": value,
        "statement_kind": statement_kind,
        "financial_scope": "consolidated",
        "table_id": table_id,
        "table_instance_id": table_id,
        "table_group_id": table_id,
        "scale": "million",
        "currency": "USD",
        "text": f"{row_label} {period} {value} million USD",
    }


def _turnover_evidence() -> list[dict[str, Any]]:
    return [
        _operations_parent(),
        _revenue_child(),
        _operand(
            "net-ppe-2018",
            "Property and equipment, net",
            "282",
            "2018",
            statement_kind="balance_sheet",
            table_id="balance-sheet",
        ),
        _operand(
            "net-ppe-2019",
            "Property and equipment, net",
            "253",
            "2019",
            statement_kind="balance_sheet",
            table_id="balance-sheet",
        ),
    ]


def _question() -> str:
    return (
        "What is the FY2019 fixed asset turnover ratio? Fixed asset turnover "
        "is FY2019 revenue divided by average PP&E for FY2018 and FY2019."
    )


def _selected_plan(
    question: str,
    revenue: dict[str, Any],
    ppe: list[dict[str, Any]],
) -> dict[str, Any]:
    return bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        [revenue, *ppe],
    ).as_dict()


def test_cross_parser_atomic_cell_reconciliation_restores_local_revenue_scale() -> None:
    question = _question()
    parent, revenue, *ppe = _turnover_evidence()
    answer = finance_numeric_answer(
        question,
        [parent, revenue, *ppe],
        query_plan=_selected_plan(question, revenue, ppe),
    )

    assert answer is not None
    assert not answer.calculation_verification["errors"]
    assert answer.calculation_verification["valid"] is True
    assert answer.calculation_execution["status"] == "ok"
    assert answer.answer == "24.26"
    operands = {
        operand["query_slot_id"]: operand
        for operand in answer.calculation_plan["operands"]
    }
    assert {operand["scale"] for operand in operands.values()} == {"million"}
    revenue_operand = operands["operand:net_sales:2019"]
    assert revenue_operand["value"] == "6489.0"
    assert parent["evidence_id"] in revenue_operand["evidence_id"]
    assert parent["evidence_id"] in revenue_operand["scale_evidence_identity"]
    dimension_slot = next(
        slot
        for slot in answer.authoritative_query_plan["evidence_slots"]
        if slot["slot_id"] == "dimension:scale"
    )
    assert dimension_slot["status"] == "filled"
    assert set(dimension_slot["applied_query_slot_ids"]) == set(operands)
    assert len(dimension_slot["evidence_ids"]) >= 2
    assert revenue_operand["scale_evidence_identity"] in dimension_slot["evidence_ids"]


def test_cross_parser_atomic_cell_reconciliation_rejects_semantic_mismatch() -> None:
    parent = _operations_parent()
    mismatches: tuple[dict[str, Any], ...] = (
        {"row_index": 2},
        {"row_label": "Net revenues excluding subscriptions"},
        {"period": "2018"},
        {"value": "9999"},
    )

    for updates in mismatches:
        child = _revenue_child(**updates)
        items = calculation_evidence_items([parent, child])
        assert identity_of(child).key in {identity_of(item).key for item in items}


def test_cross_parser_atomic_cell_reconciliation_rejects_ambiguous_parents() -> None:
    child = _revenue_child()
    items = calculation_evidence_items(
        [
            _operations_parent("operations-image-parent-a"),
            _operations_parent("operations-image-parent-b"),
            child,
        ]
    )

    assert identity_of(child).key in {identity_of(item).key for item in items}


def test_cross_parser_atomic_cell_reconciliation_requires_strict_missing_coordinate_match() -> (
    None
):
    child = _revenue_child(row_index=None, column_index=None)
    items = calculation_evidence_items([_operations_parent(), child])
    identities = {identity_of(item).key for item in items}

    assert identity_of(child).key not in identities
    replacement = next(
        item
        for item in items
        if item.get("row_label") == "Total net revenues"
        and item.get("period") == "2019"
        and item.get("scale") == "million"
    )
    assert replacement["materialization_source_id"] == "operations-image-parent"


def test_cross_parser_atomic_cell_reconciliation_keeps_complete_binding() -> None:
    complete = _revenue_child(
        scale="million",
        text="Total net revenues 2019 6489 million USD consolidated data",
    )
    items = calculation_evidence_items([_operations_parent(), complete])

    assert identity_of(complete).key in {identity_of(item).key for item in items}


def test_fixed_asset_turnover_rejects_missing_or_conflicting_local_scale() -> None:
    question = _question()
    _parent, revenue, *ppe = _turnover_evidence()
    query_plan = _selected_plan(question, revenue, ppe)
    missing = finance_numeric_answer(
        question,
        [revenue, *ppe],
        query_plan=query_plan,
    )
    conflicting = finance_numeric_answer(
        question,
        [_operations_parent(scale="thousands"), revenue, *ppe],
        query_plan=query_plan,
    )

    assert missing is not None
    assert conflicting is not None
    assert (
        "required_slot_missing:dimension:scale"
        in missing.calculation_verification["errors"]
    )
    assert missing.calculation_execution["status"] == "error"
    assert conflicting.calculation_execution["status"] == "error"


def test_cross_parser_reconciliation_does_not_select_revenue_component() -> None:
    question = _question()
    parent, revenue, *ppe = _turnover_evidence()
    component = _operand(
        "subscription-revenues-2019",
        "Subscription, licensing, and other revenues",
        "4514",
        "2019",
        statement_kind="income_statement",
        table_id="local-operations",
    )
    answer = finance_numeric_answer(
        question,
        [parent, component, revenue, *ppe],
        query_plan=_selected_plan(question, revenue, ppe),
    )

    assert answer is not None
    revenue_operand = next(
        operand
        for operand in answer.calculation_plan["operands"]
        if operand["query_slot_id"] == "operand:net_sales:2019"
    )
    assert revenue_operand["value"] == "6489.0"
