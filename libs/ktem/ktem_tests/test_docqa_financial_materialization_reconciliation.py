from decimal import Decimal
from typing import Any

from ktem.docqa.calculation_evidence_identity import (
    calculation_evidence_items,
    calculation_evidence_lookup,
)
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan


def test_parent_table_replaces_stale_materialized_component_scope():
    parent_id = "element:report:111:table-income"
    stale_component = {
        "evidence_id": (
            "source:report#page:111#table-instance:table-income#block:income"
            "#row:2#column:1"
        ),
        "source_id": "report",
        "page_label": "111",
        "table_id": "table-income",
        "table_instance_id": "table-income",
        "block_id": "income",
        "materialization_source_id": parent_id,
        "evidence_level": "cell",
        "cell_role": "data",
        "row_index": 2,
        "column_index": 1,
        "row_label": "Cost of products sold",
        "column_label": "2019",
        "period": "2019",
        "value": "6251",
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
        "text": "Cost of products sold 2019 6251 million consolidated",
    }
    parent = {
        "evidence_id": parent_id,
        "element_id": "table-income",
        "source_id": "report",
        "page_label": "111",
        "table_id": "table-income",
        "table_instance_id": "table-income",
        "block_id": "income",
        "text": (
            "Condensed Consolidating Statements of Income\n"
            "For the Year Ended December 28, 2019\n(in millions)\n"
            "Parent Guarantor Subsidiary Issuer Non-Guarantor Subsidiaries "
            "Eliminations Consolidated\n"
            "Cost of products sold — 11,042 6,251 (463) 16,830"
        ),
    }
    question = (
        "What is FY2019 inventory turnover, defined as FY2019 COGS divided by "
        "average FY2018 and FY2019 inventory?"
    )

    bound = bind_evidence_slots(
        build_query_plan(
            question, answer_type="numeric", verification_domain="finance"
        ),
        [stale_component, parent],
    )
    cogs = next(
        slot for slot in bound.evidence_slots if slot.metric == "cost of goods sold"
    )
    lookup = calculation_evidence_lookup([stale_component, parent])
    selected = lookup[cogs.evidence_ids[0]]

    assert selected["value"] == "16830"
    assert selected["financial_scope"] == "consolidated"
    assert selected["metadata"]["column_header_path"][0] == "Consolidated"


def _structured_cell(
    evidence_id: str,
    row_label: str,
    value: str,
    period: str,
    *,
    statement_kind: str = "income_statement",
    financial_scope: str = "consolidated",
    scale: str = "million",
    table_id: str = "table-d89",
    table_instance_id: str = "table-d89",
    block_id: str = "income",
    source_id: str = "report-07966",
    page_label: str = "d89",
    row_index: int = 1,
    column_index: int = 1,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "canonical_id": f"cell:{source_id}:{evidence_id}",
        "source_id": source_id,
        "file_id": source_id,
        "page_label": page_label,
        "table_id": table_id,
        "table_instance_id": table_instance_id,
        "table_group_id": table_id,
        "block_id": block_id,
        "materialization_source_id": table_id,
        "parent_element_id": table_id,
        "evidence_level": "cell",
        "cell_role": "data",
        "cell_id": evidence_id,
        "row_index": row_index,
        "column_index": column_index,
        "row_label": row_label,
        "column_label": period,
        "period": period,
        "value": value,
        "scale": scale,
        "currency": "USD",
        "statement_kind": statement_kind,
        "financial_scope": financial_scope,
        "text": f"{row_label} {period} {value} {scale} USD",
    }


def test_child_only_materialized_cell_is_retained() -> None:
    child = _structured_cell(
        "net-revenues-2017",
        "Net revenues",
        "7017",
        "2017",
        row_index=1,
        column_index=1,
    )

    lookup = calculation_evidence_lookup([child])

    assert identity_of(child).key in lookup
    assert lookup[identity_of(child).key]["value"] == "7017"


def test_mixed_page_without_real_parent_keeps_atomic_child() -> None:
    page = {
        "evidence_id": "page-d89",
        "element_id": "page-d89",
        "source_id": "report-07966",
        "page_label": "d89",
        "evidence_level": "page",
        "text": "Entity overview and selected financial data; all amounts are in millions.",
    }
    child = _structured_cell(
        "net-revenues-2017",
        "Net revenues",
        "7017",
        "2017",
        row_index=1,
        column_index=1,
    )

    lookup = calculation_evidence_lookup([page, child])

    assert identity_of(child).key in lookup


def test_non_equivalent_parent_does_not_delete_executable_child() -> None:
    child = _structured_cell(
        "net-revenues-2017",
        "Net revenues",
        "7017",
        "2017",
        row_index=1,
        column_index=1,
    )
    parent = {
        "evidence_id": "table-d89",
        "element_id": "table-d89",
        "source_id": "report-07966",
        "page_label": "d89",
        "table_id": "table-d89",
        "table_instance_id": "table-d89",
        "block_id": "income",
        "modality": "table",
        "text": ("Consolidated Balance Sheets\n" "2017\n" "Inventories 999"),
    }

    lookup = calculation_evidence_lookup([child, parent])

    assert identity_of(child).key in lookup
    assert lookup[identity_of(child).key]["value"] == "7017"


def _07966_like_evidence() -> list[dict[str, Any]]:
    page = {
        "evidence_id": "page-d89",
        "element_id": "page-d89",
        "source_id": "report-07966",
        "page_label": "d89",
        "evidence_level": "page",
        "text": (
            "Selected financial data for Entity 07966. "
            "All amounts in the following tables are in millions unless otherwise noted."
        ),
    }
    evidence: list[dict[str, Any]] = [page]
    for column_index, (period, capex, revenue) in enumerate(
        (("2017", "-155", "7017"), ("2018", "-131", "7500"), ("2019", "-116", "6489")),
        start=1,
    ):
        evidence.extend(
            (
                _structured_cell(
                    f"capex-{period}",
                    "Capital expenditures",
                    capex,
                    period,
                    statement_kind="cash_flow_statement",
                    scale="million",
                    block_id="cash-flow",
                    row_index=1,
                    column_index=column_index,
                ),
                _structured_cell(
                    f"net-revenues-{period}",
                    "Net revenues",
                    revenue,
                    period,
                    statement_kind="income_statement",
                    scale="",
                    block_id="income",
                    row_index=1,
                    column_index=column_index,
                ),
            )
        )
    return evidence


def test_07966_like_child_only_ratio_is_filled_verified_and_cited() -> None:
    question = (
        "What is the FY2017 - FY2019 3 year average of capex as a % of "
        "revenue? Answer in units of percents and round to one decimal place."
    )
    evidence = _07966_like_evidence()
    expanded = calculation_evidence_items(evidence)
    plan = bind_evidence_slots(
        build_query_plan(
            question, answer_type="numeric", verification_domain="finance"
        ),
        expanded,
    )
    answer = finance_numeric_answer(question, expanded, query_plan=plan.as_dict())

    assert all(
        slot.status == "filled"
        for slot in plan.evidence_slots
        if slot.required_for_execution and slot.role == "operand"
    )
    assert answer is not None
    assert answer.answer == "1.9%"
    assert answer.calculation_verification["valid"] is True
    operands = {
        operand["query_slot_id"]: operand
        for operand in answer.calculation_plan["operands"]
    }
    lookup = calculation_evidence_lookup(expanded)
    expected_values = {
        "operand:capital_expenditure:2017": Decimal("-155"),
        "operand:net_sales:2017": Decimal("7017"),
        "operand:capital_expenditure:2018": Decimal("-131"),
        "operand:net_sales:2018": Decimal("7500"),
        "operand:capital_expenditure:2019": Decimal("-116"),
        "operand:net_sales:2019": Decimal("6489"),
    }
    for slot_id, expected in expected_values.items():
        source_cell = lookup[operands[slot_id]["evidence_identity"]]
        assert Decimal(str(source_cell["value"])) == expected
    assert {
        slot_id: Decimal(operands[slot_id]["value"]) for slot_id in expected_values
    } == {
        "operand:capital_expenditure:2017": Decimal("155"),
        "operand:net_sales:2017": Decimal("7017"),
        "operand:capital_expenditure:2018": Decimal("131"),
        "operand:net_sales:2018": Decimal("7500"),
        "operand:capital_expenditure:2019": Decimal("116"),
        "operand:net_sales:2019": Decimal("6489"),
    }
    citation_ids = answer.calculation_verification["citation_ids"]
    assert citation_ids
    assert all(citation_id in lookup for citation_id in citation_ids)
