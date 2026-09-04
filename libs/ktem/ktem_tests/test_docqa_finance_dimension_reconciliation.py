from __future__ import annotations

from typing import Any

from ktem.docqa.calculation_evidence_identity import calculation_evidence_lookup
from ktem.docqa.evidence_identity import exact_evidence_aliases, identity_of
from ktem.docqa.evidence_set_selection import select_evidence_for_plan
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.finance_query_plan_answer import bind_numeric_query_plan
from ktem.docqa.finance_scale import source_scale_evidence
from ktem.docqa.financial_table import parse_financial_table_cells
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan

from .test_docqa_execution_binding_regressions import _multi_period_ratio_evidence
from .test_docqa_execution_slot_lineage_contract import _cell


def _capex_evidence(*, scale: str) -> tuple[dict[str, Any], dict[str, Any]]:
    parent = {
        "evidence_id": "cash-flow-parent",
        "canonical_id": "element:report:cash-flow-parent",
        "source_id": "report",
        "page_label": "49",
        "element_type": "table",
        "table_instance_id": "cash-flow",
        "table_group_id": "cash-flow",
        "statement_kind": "cash_flow_statement",
        "financial_scope": "consolidated",
        "text": "Consolidated statements of cash flows",
    }
    cell = {
        **_cell(
            "capex-2018",
            "Purchases of property, plant and equipment (PP&E)",
            "-1577",
            period="2018",
        ),
        "page_label": "49",
        "table_id": "cash-flow",
        "table_instance_id": "cash-flow",
        "table_group_id": "cash-flow",
        "materialization_source_id": "cash-flow-parent",
        "statement_kind": "cash_flow_statement",
        "scale": scale,
        "currency": "USD",
        "text": (
            "Purchases of property, plant and equipment (PP&E) 2018 -1577 "
            f"{scale} USD"
        ),
    }
    return parent, cell


def test_cell_scale_provenance_reconciles_dimension_before_verification() -> None:
    question = "What was FY2018 capital expenditure in USD millions?"
    parent, cell = _capex_evidence(scale="million")
    cell_identity = identity_of(cell).key

    assert source_scale_evidence(cell, [parent, cell]) == (
        "million",
        "capex-2018",
    )
    selected_plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        [parent, cell],
    )
    dimension = next(
        slot for slot in selected_plan.evidence_slots if slot.role == "dimension"
    )
    assert dimension.evidence_ids == (cell_identity,)

    answer = finance_numeric_answer(
        question,
        [parent, cell],
        query_plan=selected_plan.as_dict(),
    )

    assert answer is not None
    assert answer.answer == "$1,577 million"
    assert answer.calculation_execution["status"] == "ok"
    assert answer.calculation_execution["value"] == "1577"
    assert answer.calculation_verification["valid"] is True
    assert answer.authoritative_query_plan["state_authority"] == (
        "verified_calculation_plan"
    )
    authoritative_dimension = next(
        slot
        for slot in answer.authoritative_query_plan["evidence_slots"]
        if slot["slot_id"] == "dimension:scale"
    )
    assert authoritative_dimension["evidence_ids"] == [cell_identity]
    [operand] = answer.calculation_plan["operands"]
    assert operand["evidence_identity"] == cell_identity
    assert operand["scale_evidence_identity"] == cell_identity


def test_missing_real_scale_provenance_still_fails_closed() -> None:
    question = "What was FY2018 capital expenditure in USD millions?"
    parent, cell = _capex_evidence(scale="")
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        [parent, cell],
    )

    answer = finance_numeric_answer(
        question,
        [parent, cell],
        query_plan=plan.as_dict(),
    )

    assert answer is not None
    assert answer.answer == ""
    assert answer.calculation_execution["status"] == "error"
    assert "required_slot_missing:dimension:scale" in (
        answer.calculation_verification["errors"]
    )


def test_parent_header_scale_binds_to_atomic_ppe_cell_by_parent_identity() -> None:
    question = "What was FY2018 net property, plant and equipment in USD millions?"
    parent = {
        "evidence_id": "ppe-table-parent",
        "element_id": "ppe-table-parent",
        "source_id": "boeing",
        "page_label": "90",
        "element_type": "table",
        "text": "Consolidated balance sheets (in millions)",
    }
    cell = {
        **_cell(
            "ppe-2018",
            "Property, plant and equipment, net",
            "12645",
            period="2018",
        ),
        "source_id": "boeing",
        "page_label": "90",
        "parent_element_id": "ppe-table-parent",
        "table_id": "ppe-table-parent",
        "table_instance_id": "ppe-table-parent",
        "statement_kind": "balance_sheet",
        "financial_scope": "consolidated",
        "scale": "",
        "text": "Property, plant and equipment, net 2018 12645 USD",
    }

    assert source_scale_evidence(cell, [parent, cell]) == (
        "million",
        "ppe-table-parent",
    )
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        [parent, cell],
    )
    dimension = next(slot for slot in plan.evidence_slots if slot.role == "dimension")
    assert dimension.status == "filled"
    assert dimension.evidence_ids == (identity_of(parent).key,)

    answer = finance_numeric_answer(
        question,
        [parent, cell],
        query_plan=plan.as_dict(),
    )

    assert answer is not None
    assert answer.answer == "$12,645 million"
    assert answer.calculation_verification["valid"] is True


def test_bind_numeric_query_plan_replaces_only_unresolved_binding() -> None:
    question = "What were FY2019 net sales?"
    total = {
        **_cell("net-revenues", "Net revenues", "6489", period="2019"),
        "statement_kind": "income_statement",
        "text": "Net revenues 2019 6489 million USD",
    }
    component = {
        **_cell(
            "subscription-revenues",
            "Subscription, licensing, and other revenues",
            "4514",
            period="2019",
        ),
        "statement_kind": "income_statement",
        "text": "Subscription, licensing, and other revenues 2019 4514 million USD",
    }
    plan = build_query_plan(
        question,
        answer_type="numeric",
        verification_domain="finance",
    ).as_dict()
    [slot] = [item for item in plan["evidence_slots"] if item["role"] == "operand"]
    slot["status"] = "filled"
    slot["evidence_ids"] = ["cell:report:missing"]

    rebound = bind_numeric_query_plan(question, [component, total], plan)

    assert rebound is not None
    rebound_slot = next(
        item for item in rebound["evidence_slots"] if item["role"] == "operand"
    )
    assert rebound_slot["evidence_ids"] == [identity_of(total).key]
    trace = next(
        item for item in rebound["binding_trace"] if item["slot_id"] == slot["slot_id"]
    )
    assert trace["preserved_existing_binding"] is False
    assert trace["replacement_reason"] == "unresolved_existing_identity"
    assert trace["before_identity"] == "cell:report:missing"
    assert trace["after_identity"] == identity_of(total).key


def test_selection_keeps_linked_dimensions_when_context_budget_is_full() -> None:
    question = (
        "What is the FY2017 - FY2019 3 year average of capex as a % of revenue? "
        "Answer in units of percents and round to one decimal place."
    )
    evidence = _multi_period_ratio_evidence()
    for index, item in enumerate(evidence):
        item["reranker_score"] = 100 - index
    evidence[0]["reranker_score"] = -100
    evidence.extend(
        {
            "evidence_id": f"distractor-{index}",
            "source_id": "report",
            "page_label": str(100 + index % 5),
            "text": f"capex revenue 2017 2018 2019 average percent {index}",
            "reranker_score": 1000 - index,
        }
        for index in range(80)
    )

    selected, _trace, _bound = select_evidence_for_plan(
        question,
        evidence,
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
    )

    assert "selected-financial-data-page" in {item["evidence_id"] for item in selected}


def test_scale_binding_matches_prefixed_table_identity_to_page_table():
    question = (
        "What is Boeing's year end FY2018 net property, plant, and equipment "
        "in USD millions?"
    )
    cell = {
        **_cell(
            "ppe-2018",
            "Property, plant and equipment, net",
            "12645",
            period="2018",
        ),
        "source_id": "boeing",
        "page_label": "52",
        "table_id": "table-balance-uuid",
        "table_instance_id": "table-balance-uuid",
        "statement_kind": "balance_sheet",
        "financial_scope": "consolidated",
        "text": "Property, plant and equipment, net 2018 12645 USD",
    }
    page_table = {
        "evidence_id": "balance-uuid",
        "element_id": "balance-uuid",
        "source_id": "boeing",
        "page_label": "52",
        "text": (
            "Consolidated Statements of Financial Position "
            "(Dollars in millions, except per share data)"
        ),
    }

    bound = bind_evidence_slots(
        build_query_plan(
            question, answer_type="numeric", verification_domain="finance"
        ),
        [cell, page_table],
    )
    dimension = next(slot for slot in bound.evidence_slots if slot.role == "dimension")

    assert dimension.status == "filled"
    assert dimension.evidence_ids == (identity_of(page_table).key,)


def test_malformed_cell_identity_is_reconciled_to_physical_identity_with_alias():
    malformed = {
        "evidence_id": "legacy-cell-record",
        "file_id": "report-file",
        "page_label": "68",
        "element_type": "table",
        "table_id": "balance-sheet",
        "table_instance_id": "balance-sheet-instance",
        "block_id": "balance-sheet-block",
        "row_index": 1,
        "column_index": 1,
        "cell_id": "source:report-file#page:1#table-instance:old#row:9#column:9",
        "row_label": "Total current assets",
        "column_label": "2021",
        "period": "2021",
        "value": "19815",
        "scale": "million",
        "statement_kind": "balance_sheet",
        "text": "Total current assets 2021 19815 million",
    }

    [cell] = parse_financial_table_cells(malformed)
    expected_identity = cell.physical_identity.key
    lookup = calculation_evidence_lookup([malformed])

    assert cell.cell_id == expected_identity
    assert expected_identity in lookup
    assert malformed["cell_id"] in exact_evidence_aliases(lookup[expected_identity])


def test_current_liability_cell_reconciles_stale_cash_flow_statement_kind():
    item = {
        "evidence_id": "legacy-liability-cell",
        "file_id": "report-file",
        "page_label": "68",
        "element_type": "table",
        "evidence_level": "cell",
        "table_id": "balance-sheet",
        "table_instance_id": "balance-sheet-instance",
        "block_id": "balance-sheet-block",
        "row_index": 2,
        "column_index": 1,
        "cell_id": "legacy-liability-cell",
        "row_label": "Total current liabilities",
        "column_label": "2021",
        "period": "2021",
        "value": "13997",
        "scale": "million",
        "statement_kind": "cash_flow_statement",
        "text": "Total current liabilities 2021 13997 million cash flow statement",
    }

    [cell] = parse_financial_table_cells(item)

    assert cell.statement_kind == "balance_sheet"


def test_only_placeholder_source_id_keeps_legacy_identity_value():
    item = {
        "evidence_id": "legacy-element",
        "source_id": "unknown",
        "page_label": "68",
        "element_id": "legacy-element",
        "text": "A legacy evidence record.",
    }

    assert identity_of(item).source_id == "unknown"


def test_file_id_reconciles_placeholder_source_for_dimension_and_lineage():
    item = {
        "evidence_id": "legacy-cell",
        "source_id": "unknown",
        "file_id": "report-file",
        "page_label": "4",
        "table_instance_id": "balance-sheet",
        "text": "Total current assets 2021 100 million",
    }
    dimension = {
        "evidence_id": "table-header",
        "file_id": "report-file",
        "page_label": "4",
        "table_instance_id": "balance-sheet",
        "text": "Consolidated balance sheet (in millions)",
    }

    assert source_scale_evidence(item, [item, dimension]) == (
        "million",
        "table-header",
    )
