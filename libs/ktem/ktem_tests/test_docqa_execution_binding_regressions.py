from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_set_selection import select_evidence_for_plan
from ktem.docqa.execution_slot_lineage import linked_dimension_candidate
from ktem.docqa.finance_calculation_adapter import finance_calculation_audit
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


def test_execution_slot_preferred_evidence_cannot_leak_to_global_pool() -> None:
    question = "What were FY2021 net sales?"
    selected = {
        **_cell("selected-sales", "Net sales", "100", period="2021"),
        "statement_kind": "income_statement",
    }
    leaked = {
        **_cell("leaked-sales", "Net sales", "999", period="2021"),
        "statement_kind": "income_statement",
    }
    query_plan = build_query_plan(
        question,
        answer_type="numeric",
        verification_domain="finance",
    ).as_dict()
    [slot] = [
        item
        for item in query_plan["evidence_slots"]
        if item["slot_id"].startswith("operand:")
    ]
    slot["status"] = "filled"
    slot["evidence_ids"] = [identity_of(selected).key]

    audit = finance_calculation_audit(
        question,
        [selected, leaked],
        question_type="net_sales",
        inputs={"net_sales_2021": 999.0},
        query_plan=query_plan,
    )

    [operand] = audit.plan.as_dict()["operands"]
    assert operand["evidence_identity"] == identity_of(selected).key
    assert operand["value"] == "100"


def test_calculation_inputs_bind_to_slot_ids_not_slot_position() -> None:
    question = (
        "What was FY2021 working capital, defined as current assets less "
        "current liabilities?"
    )
    assets = _cell("assets", "Current assets", "20991", period="2021")
    liabilities = _cell(
        "liabilities",
        "Current liabilities",
        "15173",
        period="2021",
    )
    bound = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        [assets, liabilities],
    )

    audit = finance_calculation_audit(
        question,
        [assets, liabilities],
        question_type="working_capital",
        inputs={"current_liabilities": 15173, "current_assets": 20991},
        query_plan=bound.as_dict(),
    )

    operands = {
        operand["query_slot_id"]: operand
        for operand in audit.plan.as_dict()["operands"]
    }
    assert operands["operand:current_assets"]["evidence_identity"] == (
        identity_of(assets).key
    )
    assert operands["operand:current_liabilities"]["evidence_identity"] == (
        identity_of(liabilities).key
    )


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
    authoritative = answer.as_trace()["authoritative_query_plan"]
    operand_slot = next(
        slot for slot in authoritative["evidence_slots"] if slot["role"] == "operand"
    )
    dimension_slot = next(
        slot for slot in authoritative["evidence_slots"] if slot["role"] == "dimension"
    )
    assert operand_slot["scale"] == "million"
    assert operand_slot["statement_kind"] == "cash_flow_statement"
    assert operand_slot["table_instance_id"] == "cash-flow-table"
    assert dimension_slot["scale"] == "million"
    assert dimension_slot["evidence_ids"] == [identity_of(parent).key]


def test_extractive_finance_cell_becomes_typed_execution_authority() -> None:
    question = "What was adjusted EBITDA in FY2023?"
    cell = {
        **_cell("adjusted-ebitda", "Adjusted EBITDA", "1250", period="2023"),
        "statement_kind": "non_gaap_performance",
        "financial_scope": "consolidated",
        "text": (
            "Consolidated non-GAAP financial measure Adjusted EBITDA " "2023 1250 USD"
        ),
    }
    plan = build_query_plan(
        question,
        answer_type="extractive",
        verification_domain="finance",
    )

    answer = finance_numeric_answer(
        question,
        [cell],
        query_plan=plan.as_dict(),
    )

    assert answer is not None
    assert answer.attempt_status == "executed"
    assert answer.calculation_verification["valid"] is True
    assert answer.calculation_execution["status"] == "ok"
    assert answer.authoritative_query_plan["state_authority"] == (
        "verified_calculation_plan"
    )


def test_extractive_finance_cell_with_wrong_statement_scope_fails_closed() -> None:
    question = "What was adjusted EBITDA in FY2023?"
    compensation_cell = {
        **_cell("compensation", "Adjusted EBITDA", "2018", period="2023"),
        "statement_kind": "compensation_or_benefit_table",
        "financial_scope": "",
        "text": "Executive compensation Adjusted EBITDA 2023 2018",
    }

    answer = finance_numeric_answer(
        question,
        [compensation_cell],
        query_plan=build_query_plan(
            question,
            answer_type="extractive",
            verification_domain="finance",
        ).as_dict(),
    )

    assert answer is not None
    assert answer.calculation_execution["status"] != "ok"
    assert answer.answer == ""


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


def _turnover_cell(
    evidence_id: str,
    row_label: str,
    value: str,
    period: str,
    *,
    statement_kind: str,
    table_id: str,
) -> dict[str, Any]:
    return {
        **_cell(evidence_id, row_label, value, period=period),
        "page_label": "37" if statement_kind == "income_statement" else "69",
        "table_id": table_id,
        "table_instance_id": table_id,
        "table_group_id": table_id,
        "materialization_source_id": "",
        "statement_kind": statement_kind,
        "scale": "million",
        "currency": "USD",
        "text": f"{row_label} {period} {value} million USD",
    }


def _fixed_asset_turnover_evidence() -> list[dict[str, Any]]:
    return [
        _turnover_cell(
            "net-revenues-2019",
            "Net revenues",
            "6489",
            "2019",
            statement_kind="income_statement",
            table_id="income",
        ),
        _turnover_cell(
            "subscription-revenues-2019",
            "Subscription, licensing, and other revenues",
            "4514",
            "2019",
            statement_kind="income_statement",
            table_id="income",
        ),
        _turnover_cell(
            "net-ppe-2018",
            "Property and equipment, net",
            "282",
            "2018",
            statement_kind="balance_sheet",
            table_id="balance-sheet",
        ),
        _turnover_cell(
            "net-ppe-2019",
            "Property and equipment, net",
            "253",
            "2019",
            statement_kind="balance_sheet",
            table_id="balance-sheet",
        ),
    ]


def test_execution_preserves_selected_total_revenue_binding() -> None:
    question = (
        "What is the FY2019 fixed asset turnover ratio? Fixed asset turnover "
        "is FY2019 revenue divided by average PP&E for FY2018 and FY2019."
    )
    evidence = _fixed_asset_turnover_evidence()
    selected_plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        evidence,
    )
    revenue_slot = next(
        slot
        for slot in selected_plan.evidence_slots
        if slot.slot_id == "operand:net_sales:2019"
    )
    selected_identity = identity_of(evidence[0]).key
    assert revenue_slot.evidence_ids == (selected_identity,)

    answer = finance_numeric_answer(
        question,
        [evidence[1], evidence[0], *evidence[2:]],
        query_plan=selected_plan.as_dict(),
    )

    assert answer is not None
    assert answer.answer == "24.26"
    authoritative_slot = next(
        slot
        for slot in answer.authoritative_query_plan["evidence_slots"]
        if slot["slot_id"] == "operand:net_sales:2019"
    )
    assert authoritative_slot["evidence_ids"] == [selected_identity]
    trace = answer.authoritative_query_plan["binding_trace"]
    revenue_trace = next(
        item for item in trace if item["slot_id"] == "operand:net_sales:2019"
    )
    assert revenue_trace == {
        "slot_id": "operand:net_sales:2019",
        "preserved_existing_binding": True,
        "replacement_reason": "",
        "before_identity": selected_identity,
        "after_identity": selected_identity,
    }


def test_revenue_binding_distinguishes_rollups_from_components() -> None:
    question = "What were FY2019 net sales?"
    total, component = _fixed_asset_turnover_evidence()[:2]
    generic = _turnover_cell(
        "generic-revenue-2019",
        "Revenues",
        "6000",
        "2019",
        statement_kind="income_statement",
        table_id="income",
    )

    def bound_id(items: list[dict[str, Any]]) -> tuple[str, ...]:
        plan = bind_evidence_slots(
            build_query_plan(
                question,
                answer_type="numeric",
                verification_domain="finance",
            ),
            items,
        )
        return next(
            slot for slot in plan.evidence_slots if slot.role == "operand"
        ).evidence_ids

    assert bound_id([component, total]) == (identity_of(total).key,)
    assert bound_id([total]) == (identity_of(total).key,)
    assert bound_id([generic]) == (identity_of(generic).key,)
    assert bound_id([component]) == ()
    second_component = {
        **component,
        "evidence_id": "product-revenue",
        "canonical_id": "cell:report:product-revenue",
        "cell_id": "product-revenue",
        "row_label": "Product revenues",
        "text": "Product revenues 2019 1975 million USD",
    }
    assert bound_id([component, second_component]) == ()
