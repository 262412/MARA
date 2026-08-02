from __future__ import annotations

from ktem.docqa.evidence_set_selection import select_evidence_for_plan
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan

from .test_docqa_evidence_set_selection import _cell_item, _item


def test_selected_candidate_is_not_reported_as_bound_without_slot_identity() -> None:
    plan = QueryPlan(
        answer_type="numeric",
        question_type="numeric",
        evidence_slots=(
            EvidenceSlot(
                slot_id="operand:current_assets:2021",
                role="operand",
                metric="current assets",
                period="2021",
                statement_kind="balance_sheet",
                financial_scope="consolidated",
                required_for_execution=True,
            ),
        ),
        constraints={"requires_structure": True},
    )
    compatible = _cell_item(
        "compatible",
        "10",
        "Consolidated current assets 2021 100 million.",
        0.9,
        row_label="Current assets",
        period="2021",
        value="100",
    )
    compatible["statement_kind"] = "balance_sheet"
    selected_noise = _item("narrative", "11", "Current assets discussion.", 1.0)

    _selected, trace, _bound = select_evidence_for_plan(
        "current assets 2021",
        [selected_noise, compatible],
        plan,
    )

    [binding] = trace["required_slot_bindings"]
    selected_reasons = {
        item["evidence_id"]: item["reason"]
        for item in binding["candidate_selection_reasons"]
    }
    assert "semantic_slot_match_selected" not in selected_reasons.values()
    assert selected_reasons["cell:report:compatible"] == "bound_to_slot"
    assert binding["selected_evidence_ids"] == ["cell:report:compatible"]


def test_parent_reservation_is_independent_of_existing_atomic_cell() -> None:
    plan = QueryPlan(
        answer_type="numeric",
        question_type="numeric",
        evidence_slots=(
            EvidenceSlot(
                slot_id="operand:capital_expenditure:2018",
                role="operand",
                metric="capital expenditure",
                period="2018",
                statement_kind="cash_flow_statement",
                financial_scope="consolidated",
                required_for_execution=True,
            ),
        ),
        constraints={"requires_structure": True},
    )
    parent = {
        **_item(
            "cash-flow-parent",
            "49",
            "Purchases of property, plant and equipment (PP&E) (1,577)",
            0.1,
        ),
        "modality": "table",
        "table_id": "cash-flow-table",
        "statement_kind": "cash_flow_statement",
        "financial_scope": "consolidated",
    }

    selected, trace, bound = select_evidence_for_plan(
        "capital expenditure 2018",
        [parent],
        plan,
    )

    assert [item["evidence_id"] for item in selected] == ["cash-flow-parent"]
    assert bound.evidence_slots[0].status == "missing"
    assert trace["selected_budget_usage"]["parent_tables"] == 1
    assert trace["required_slot_bindings"][0]["retrieval_satisfied"] is True
