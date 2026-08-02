from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.finance_query_plan_answer import bind_numeric_query_plan
from ktem.docqa.finance_scale import source_scale_evidence
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan

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
    assert answer.calculation_execution["value"] == "1577000000"
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
