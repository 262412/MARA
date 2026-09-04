from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import evaluate_retrieval_quality
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.finance_scale import source_page_table_scale_evidence
from ktem.docqa.finance_typed_adequacy import ensure_finance_numeric_trace
from ktem.docqa.query_evidence_binding import (
    bind_evidence_slots,
    bind_evidence_slots_monotonic,
)
from ktem.docqa.query_plan_schema import plan_from_payload
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.retrieval_rounds import retrieve_with_rounds

QUESTION = (
    "What is the FY2019 fixed asset turnover ratio for Activision Blizzard? "
    "Fixed asset turnover ratio is defined as: FY2019 revenue / (average PP&E "
    "between FY2018 and FY2019). Round your answer to two decimal places. Base "
    "your judgments on the information provided primarily in the statement of "
    "income and the statement of financial position."
)


def _parent(
    evidence_id: str,
    page_label: str,
    table_id: str,
    text: str,
    *,
    statement_kind: str,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "activision-2019",
        "page_label": page_label,
        "table_id": table_id,
        "table_instance_id": table_id,
        "table_group_id": table_id,
        "element_type": "table",
        "evidence_level": "element",
        "modality": "table",
        "statement_kind": statement_kind,
        "financial_scope": "consolidated",
        "text": text,
    }


def _cell(
    evidence_id: str,
    page_label: str,
    table_id: str,
    row_label: str,
    period: str,
    value: str,
    *,
    statement_kind: str,
    scale: str = "",
    parent_id: str = "",
) -> dict[str, Any]:
    scale_text = f" {scale}" if scale else ""
    return {
        "evidence_id": evidence_id,
        "cell_id": evidence_id,
        "source_id": "activision-2019",
        "page_label": page_label,
        "table_id": table_id,
        "table_instance_id": table_id,
        "table_group_id": table_id,
        "materialization_source_id": parent_id,
        "evidence_level": "cell",
        "cell_role": "data",
        "modality": "table",
        "row_label": row_label,
        "column_label": period,
        "period": period,
        "period_kind": "fiscal_year",
        "value": value,
        "unit": "USD",
        "scale": scale,
        "currency": "USD",
        "statement_kind": statement_kind,
        "financial_scope": "consolidated",
        "text": f"{row_label} {period} {value}{scale_text} USD",
    }


def _unscaled_revenue() -> dict[str, Any]:
    return _cell(
        "revenue-page-37",
        "37",
        "operations-data-37",
        "Total net revenues",
        "2019",
        "6489",
        statement_kind="income_statement",
    )


def _scaled_revenue(page_label: str, table_id: str) -> list[dict[str, Any]]:
    parent_id = f"{table_id}-parent"
    return [
        _parent(
            parent_id,
            page_label,
            table_id,
            (
                "Consolidated Statements of Operations. Amounts in millions. "
                "Total net revenues 2019 6489."
            ),
            statement_kind="income_statement",
        ),
        _cell(
            f"revenue-page-{page_label}",
            page_label,
            table_id,
            "Total net revenues",
            "2019",
            "6489",
            statement_kind="income_statement",
            scale="million",
            parent_id=parent_id,
        ),
    ]


def _ppe_evidence(*, page_label: str = "69") -> list[dict[str, Any]]:
    parent_id = "balance-sheet-parent"
    table_id = "balance-sheet-69"
    return [
        _parent(
            parent_id,
            page_label,
            table_id,
            (
                "Consolidated Balance Sheets. Amounts in millions. Property and "
                "equipment, net 2019 253 2018 282."
            ),
            statement_kind="balance_sheet",
        ),
        _cell(
            "ppe-2018",
            page_label,
            table_id,
            "Property and equipment, net",
            "2018",
            "282",
            statement_kind="balance_sheet",
            scale="million",
            parent_id=parent_id,
        ),
        _cell(
            "ppe-2019",
            page_label,
            table_id,
            "Property and equipment, net",
            "2019",
            "253",
            statement_kind="balance_sheet",
            scale="million",
            parent_id=parent_id,
        ),
    ]


def _plan():
    return build_query_plan(
        QUESTION,
        answer_type="numeric",
        verification_domain="finance",
    )


def _revenue_slot_identity(plan: Any) -> str:
    return next(
        slot.evidence_ids[0]
        for slot in plan.evidence_slots
        if slot.slot_id == "operand:net_sales:2019"
    )


def test_02987_rebinds_to_local_scale_complete_revenue_and_executes_24_26() -> None:
    initial_items = [_unscaled_revenue(), *_ppe_evidence()]
    initial_plan = bind_evidence_slots(_plan(), initial_items)
    failed = finance_numeric_answer(
        QUESTION,
        initial_items,
        query_plan=initial_plan.as_dict(),
    )

    assert failed is not None
    assert failed.attempt_status == "verification_failed"
    assert "required_slot_missing:dimension:scale" in (
        failed.calculation_verification["errors"]
    )

    recovered_items = [*initial_items, *_scaled_revenue("70", "operations-70")]
    provisional = plan_from_payload(
        QUESTION,
        answer_type="numeric",
        verification_domain="finance",
        payload=failed.authoritative_query_plan,
    )
    rebound, binding_trace = bind_evidence_slots_monotonic(
        provisional,
        recovered_items,
    )
    answer = finance_numeric_answer(
        QUESTION,
        recovered_items,
        query_plan=rebound.as_dict(),
    )

    assert answer is not None
    assert answer.attempt_status == "executed"
    assert answer.answer == "24.26"
    assert _revenue_slot_identity(rebound) == identity_of(recovered_items[-1]).key
    revenue_binding = next(
        item for item in binding_trace if item["slot_id"] == "operand:net_sales:2019"
    )
    assert revenue_binding["preserved_existing_binding"] is False
    assert revenue_binding["replacement_reason"] == (
        "provenance_complete_equivalent_available"
    )
    trace = answer.as_trace()
    assert trace["calculation_verification"]["valid"] is True
    assert trace["calculation_execution"]["status"] == "ok"
    revenue_operand = next(
        operand
        for operand in trace["calculation_plan"]["operands"]
        if operand["operand_id"] == "net_sales_2019"
    )
    assert revenue_operand["evidence_identity"] == identity_of(recovered_items[-1]).key
    assert revenue_operand["scale"] == "million"
    assert revenue_operand["scale_evidence_id"] == "operations-70-parent"
    assert revenue_operand["dimension_binding_scope"] == "table"


def test_02987_ppe_scale_cannot_propagate_to_revenue_across_tables() -> None:
    revenue = _unscaled_revenue()
    evidence = [revenue, *_ppe_evidence(page_label="37")]

    assert source_page_table_scale_evidence(revenue, evidence) == ("", "")
    bound = bind_evidence_slots(_plan(), evidence)
    answer = finance_numeric_answer(QUESTION, evidence, query_plan=bound.as_dict())

    assert answer is not None
    assert answer.attempt_status == "verification_failed"
    revenue_operand = next(
        operand
        for operand in answer.calculation_plan["operands"]
        if operand["operand_id"] == "net_sales_2019"
    )
    assert revenue_operand["scale"] == ""
    assert not revenue_operand.get("scale_evidence_id")


def test_02987_equivalent_scaled_revenue_selection_is_order_independent() -> None:
    revenue_30 = _scaled_revenue("30", "operations-30")
    revenue_70 = _scaled_revenue("70", "operations-70")
    fixed = _ppe_evidence()

    first = bind_evidence_slots(_plan(), [*revenue_70, *revenue_30, *fixed])
    second = bind_evidence_slots(_plan(), [*revenue_30, *revenue_70, *fixed])

    assert _revenue_slot_identity(first) == _revenue_slot_identity(second)
    selected = next(
        item
        for item in [*revenue_30, *revenue_70]
        if identity_of(item).key == _revenue_slot_identity(first)
    )
    assert source_page_table_scale_evidence(
        selected,
        [*revenue_30, *revenue_70],
    ) == ("million", selected["materialization_source_id"])


def test_missing_calculation_dimension_routes_one_targeted_recovery() -> None:
    calls: list[tuple[int, str, str]] = []

    def retrieve(request: Any, _decision: Any) -> dict[str, Any]:
        calls.append(
            (
                request.retrieval_round_id,
                request.retrieval_slot_id,
                request.retrieval_query,
            )
        )
        if request.retrieval_round_id == 2:
            return {"evidence": _scaled_revenue("70", "operations-70")}
        return {"evidence": [_unscaled_revenue(), *_ppe_evidence()]}

    request = DocQARequest(
        prompt=QUESTION,
        controller_question=QUESTION,
        retrieval_query=QUESTION,
        task_type="numeric",
        verification_domain="finance",
        origin="benchmark",
        query_plan=_plan(),
    )
    bundle, decision = retrieve_with_rounds(
        request,
        SimpleNamespace(legacy_route="doc"),
        retrieve,
        evaluate=evaluate_retrieval_quality,
        retry_poor=True,
    )

    round_two = [call for call in calls if call[0] == 2]
    assert len(round_two) == 1
    assert round_two[0][1] == "dimension:scale"
    assert "parent table" in round_two[0][2]
    assert bundle.metadata["retrieval_rounds"] == 2
    assert decision.status == "good"
    recovery = bundle.metadata["calculation_recovery_trace"]
    assert recovery["initial_missing_slot_ids"] == ["dimension:scale"]
    assert recovery["attempt_count"] == 1
    assert recovery["final_missing_slot_ids"] == []
    assert recovery["status"] == "verified"
    assert recovery["authoritative_query_plan_state_authority"] == (
        "verified_calculation_plan"
    )
    assert recovery["authoritative_slot_evidence_ids"]["operand:net_sales:2019"] == [
        _revenue_slot_identity(request.query_plan)
    ]


def test_complete_calculation_plan_does_not_retry() -> None:
    calls: list[tuple[int, str]] = []

    def retrieve(request: Any, _decision: Any) -> dict[str, Any]:
        calls.append((request.retrieval_round_id, request.retrieval_slot_id))
        return {
            "evidence": [
                *_scaled_revenue("70", "operations-70"),
                *_ppe_evidence(),
            ]
        }

    request = DocQARequest(
        prompt=QUESTION,
        controller_question=QUESTION,
        retrieval_query=QUESTION,
        task_type="numeric",
        verification_domain="finance",
        origin="benchmark",
        query_plan=_plan(),
    )
    bundle, decision = retrieve_with_rounds(
        request,
        SimpleNamespace(legacy_route="doc"),
        retrieve,
        evaluate=evaluate_retrieval_quality,
        retry_poor=True,
    )

    assert calls
    assert all(round_id == 1 for round_id, _slot_id in calls)
    assert bundle.metadata["retrieval_rounds"] == 1
    assert decision.status == "good"
    assert "calculation_recovery_trace" not in bundle.metadata


def test_reused_failed_trace_is_revalidated_after_evidence_rebind() -> None:
    initial_items = [_unscaled_revenue(), *_ppe_evidence()]
    initial_plan = bind_evidence_slots(_plan(), initial_items)
    failed = finance_numeric_answer(
        QUESTION,
        initial_items,
        query_plan=initial_plan.as_dict(),
    )
    assert failed is not None
    assert failed.attempt_status == "verification_failed"

    request = DocQARequest(
        prompt=QUESTION,
        controller_question=QUESTION,
        task_type="numeric",
        verification_domain="finance",
        origin="benchmark",
        query_plan=plan_from_payload(
            QUESTION,
            answer_type="numeric",
            verification_domain="finance",
            payload=failed.authoritative_query_plan,
        ),
    )
    recovered_items = [*initial_items, *_scaled_revenue("70", "operations-70")]
    bundle = EvidenceBundle(
        route="doc",
        items=recovered_items,
        metadata={
            "finance_numeric_trace": failed.as_trace(),
            "query_plan": failed.authoritative_query_plan,
            "calculation_recovery_trace": {
                "contract_id": "calculation_recovery.v1",
                "action": "targeted_retrieval_materialization_rebind",
                "initial_missing_slot_ids": ["dimension:scale"],
                "attempt_count": 1,
                "status": "retrieving",
            },
        },
    )

    ensure_finance_numeric_trace(request, bundle)

    trace = bundle.metadata["finance_numeric_trace"]
    assert trace["attempt_status"] == "executed"
    assert trace["answer"] == "24.26"
    assert trace["calculation_verification"]["valid"] is True
    assert trace["calculation_execution"]["status"] == "ok"
    recovery = bundle.metadata["calculation_recovery_trace"]
    assert recovery["status"] == "verified"
    assert recovery["attempt_count"] == 1
    assert recovery["final_missing_slot_ids"] == []
