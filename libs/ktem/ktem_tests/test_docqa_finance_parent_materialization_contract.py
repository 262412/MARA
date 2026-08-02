from __future__ import annotations

from decimal import Decimal

from ktem.docqa.calculation_evidence_identity import (
    calculation_evidence_items,
    materialize_financial_cell,
)
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.financial_table import parse_financial_table_cells_with_context
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan


def _header(
    text: str = "Cash flows from investing activities\nYears ended December 31\n2018\n2017\n2016",
) -> dict[str, object]:
    return {
        "evidence_id": "header",
        "source_id": "report",
        "page_label": "46",
        "text": text,
    }


def _parent(text: str | None = None) -> dict[str, object]:
    return {
        "evidence_id": "cash-flow-parent",
        "source_id": "report",
        "page_label": "49",
        "table_id": "cash-flow-table",
        "table_instance_id": "cash-flow-table",
        "table_group_id": "cash-flow-table",
        "modality": "table",
        "text": text
        or """
        Net cash provided by operating activities
        6,439
        6,240
        6,662
        Purchases of property, plant and equipment (PP&E)
        (1,577)
        (1,373)
        (1,420)
        """,
        "source_backrefs": ["report#page:49"],
        "scale": "million",
        "financial_scope": "consolidated",
    }


def test_context_header_materializes_requested_cash_flow_cell() -> None:
    parent = _parent()

    cells = parse_financial_table_cells_with_context(parent, [_header(), parent])
    cell = next(
        value
        for value in cells
        if value.row_label == "Purchases of property, plant and equipment (PP&E)"
        and value.period == "2018"
    )
    materialized = materialize_financial_cell(parent, cell)

    assert cell.value == Decimal("-1577")
    assert cell.period != str(abs(cell.value))
    assert cell.statement_kind == "cash_flow_statement"
    assert materialized["materialization_source_id"] == "cash-flow-parent"
    assert materialized["source_backrefs"] == ["report#page:49"]


def test_wrong_statement_kind_is_not_preserved_over_cash_flow_content() -> None:
    parent = {**_parent(), "statement_kind": "balance_sheet"}

    cells = parse_financial_table_cells_with_context(parent, [_header(), parent])

    assert cells
    assert {cell.statement_kind for cell in cells} == {"cash_flow_statement"}


def test_no_reliable_period_mapping_emits_no_cells() -> None:
    parent = _parent()

    cells = parse_financial_table_cells_with_context(
        parent,
        [_header("Cash flows from investing activities"), parent],
    )

    assert cells == ()


def test_materialized_parent_executes_requested_2018_capex_value() -> None:
    question = "What was FY2018 capital expenditure in USD millions?"
    evidence = [_header(), _parent()]
    expanded = calculation_evidence_items(evidence)
    bound = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        expanded,
    )

    answer = finance_numeric_answer(
        question,
        expanded,
        query_plan=bound.as_dict(),
    )

    assert answer is not None
    assert answer.answer == "$1,577 million"
    assert answer.calculation_verification["valid"] is True
