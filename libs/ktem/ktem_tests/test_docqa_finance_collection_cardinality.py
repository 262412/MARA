from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import evaluate_retrieval_quality
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn
from ktem.docqa.finance_calculation_recovery import (
    missing_required_calculation_slot_ids,
    synchronize_calculation_recovery,
)
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_plan_schema import (
    EvidenceSlot,
    evidence_slot_references_are_bound,
    slot_binding_state,
)
from ktem.docqa.query_planning import build_query_plan, slot_coverage
from ktem.docqa.required_slot_selection import required_slot_shortlist
from ktem.docqa.retrieval_rounds import retrieve_with_rounds


def _revolving_span(
    evidence_id: str,
    facility: str,
    *,
    value: str = "4200000000",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "pepsico",
        "page_label": "2",
        "evidence_level": "span",
        "span_id": evidence_id,
        "row_label": "revolving credit capacity",
        "period": "2023",
        "value": value,
        "unit": "USD",
        "currency": "USD",
        "metric": "revolving credit capacity",
        "facility_identity": facility,
        "facility_type": facility.split(":", 1)[0],
        "agreement_lifecycle_status": "active",
        "effective_date": "2023-05-26",
        "text": (
            f"The active {facility.split(':', 1)[0].replace('_', '-')} "
            f"revolving credit agreement enables borrowing up to ${value}."
        ),
    }


def _plan(question: str) -> Any:
    return build_query_plan(
        question,
        answer_type="numeric",
        verification_domain="finance",
    )


def test_collection_cardinality_does_not_fill_duplicate_facility_identity() -> None:
    slot = EvidenceSlot(
        slot_id="operand:revolving_credit_capacity:2023",
        role="operand",
        metric="revolving credit capacity",
        period="2023",
        required_for_execution=True,
        cardinality=2,
        operator_role="collection",
        status="filled",
        evidence_ids=("span:pepsico:one", "span:pepsico:two"),
    )
    duplicate_items = [
        _revolving_span("one", "364_day:2023-05-26"),
        _revolving_span("two", "364_day:2023-05-26"),
    ]

    assert slot_binding_state(slot, duplicate_items) == "retrieved_partial"
    assert not evidence_slot_references_are_bound(slot, duplicate_items)
    distinct_items = [
        duplicate_items[0],
        _revolving_span("two", "five_year:2023-05-26"),
    ]
    assert slot_binding_state(slot, distinct_items) == "filled"
    assert evidence_slot_references_are_bound(slot, distinct_items)


def test_collection_cardinality_one_item_is_partial_and_coverage_is_below_one() -> None:
    question = (
        "As of May 26, 2023, what is the total amount PepsiCo may borrow under its "
        "unsecured revolving credit agreements?"
    )
    plan = bind_evidence_slots(
        _plan(question), [_revolving_span("one", "364_day:2023-05-26")]
    )
    [slot] = plan.evidence_slots
    assert slot.status == "retrieved_partial"
    assert slot_coverage(plan) == 0.0


def test_collection_shortlist_reserves_distinct_facilities_before_global_cutoff() -> None:
    question = (
        "As of May 26, 2023, what is the total amount PepsiCo may borrow under its "
        "unsecured revolving credit agreements?"
    )
    items = [
        _revolving_span("duplicate-1", "364_day:2023-05-26"),
        _revolving_span("duplicate-2", "364_day:2023-05-26"),
        _revolving_span("distinct", "five_year:2023-05-26"),
    ]
    selected, _restored = required_slot_shortlist(
        items, _plan(question), candidate_limit=2
    )
    assert {
        str(item["facility_identity"])
        for item in selected
        if item.get("facility_identity")
    } == {"364_day:2023-05-26", "five_year:2023-05-26"}


def test_required_execution_recovery_is_generic_and_deduplicates_missing_count() -> None:
    slot_id = "operand:revolving_credit_capacity:2023"
    authoritative = {
        "state_authority": "provisional_calculation_plan",
        "evidence_slots": [
            {
                "slot_id": slot_id,
                "role": "operand",
                "metric": "revolving credit capacity",
                "period": "2023",
                "required_for_retrieval": True,
                "required_for_execution": True,
                "cardinality": 2,
                "status": "retrieved_partial",
                "evidence_ids": ["span:pepsico:one"],
                "query": "revolving credit capacity 2023",
            }
        ],
    }
    metadata: dict[str, Any] = {
        "finance_numeric_trace": {
            "authoritative_query_plan": authoritative,
            "calculation_verification": {
                "errors": [f"required_slot_missing:{slot_id}"],
                "required_slot_ids": [slot_id],
                "verified_required_slot_ids": [],
            },
        },
        "evidence": [_revolving_span("one", "364_day:2023-05-26")],
    }
    assert missing_required_calculation_slot_ids(metadata) == (slot_id,)
    synchronize_calculation_recovery(
        SimpleNamespace(prompt="total revolving credit capacity"),
        metadata,
        authoritative,
    )
    [request] = metadata["calculation_recovery_requests"]
    assert request["slot_id"] == slot_id
    assert "exclude facility identity 364_day:2023-05-26" in request["query"]
    assert "parent table dollars scale unit convention" not in request["query"]
    assert metadata["missing_required_slot_count"] == 1


def test_collection_recovery_rebinds_second_facility_and_executes() -> None:
    question = (
        "As of May 26, 2023, what is the total amount PepsiCo may borrow under its "
        "unsecured revolving credit agreements?"
    )
    calls: list[tuple[int, str, str]] = []

    def retrieve(request: Any, _decision: Any) -> dict[str, Any]:
        calls.append(
            (
                request.retrieval_round_id,
                request.retrieval_slot_id,
                request.retrieval_query,
            )
        )
        facility = (
            "364_day:2023-05-26"
            if request.retrieval_round_id == 1
            else "five_year:2023-05-26"
        )
        return {
            "evidence": [_revolving_span(str(request.retrieval_round_id), facility)]
        }

    request = DocQARequest(
        prompt=question,
        controller_question=question,
        retrieval_query=question,
        task_type="numeric",
        verification_domain="finance",
        origin="benchmark",
        query_plan=_plan(question),
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
    assert round_two[0][1] == "operand:revolving_credit_capacity:2023"
    assert "exclude facility identity 364_day" in round_two[0][2]
    assert "parent table dollars scale unit convention" not in round_two[0][2]
    assert bundle.metadata["retrieval_rounds"] == 2
    assert decision.status == "good"
    assert bundle.metadata["calculation_recovery_trace"]["status"] == "verified"
    assert bundle.metadata["finance_numeric_trace"]["answer"] == "$8,400,000,000"


def test_collection_recovery_same_facility_abstains_after_bounded_round() -> None:
    question = (
        "As of May 26, 2023, what is the total amount PepsiCo may borrow under its "
        "unsecured revolving credit agreements?"
    )
    calls: list[int] = []

    def retrieve(request: Any, _decision: Any) -> dict[str, Any]:
        calls.append(request.retrieval_round_id)
        return {"evidence": [_revolving_span("same", "364_day:2023-05-26")]}

    request = DocQARequest(
        prompt=question,
        controller_question=question,
        retrieval_query=question,
        task_type="numeric",
        verification_domain="finance",
        origin="benchmark",
        query_plan=_plan(question),
    )
    bundle, decision = retrieve_with_rounds(
        request,
        SimpleNamespace(legacy_route="doc"),
        retrieve,
        evaluate=evaluate_retrieval_quality,
        retry_poor=True,
    )
    assert calls == [1, 2]
    assert bundle.metadata["retrieval_rounds"] == 2
    assert decision.status != "good"
    assert bundle.metadata["finance_numeric_trace"]["attempt_status"] != "executed"
    assert bundle.metadata["calculation_recovery_trace"]["status"] == "failed"


def test_collection_recovery_same_facility_reaches_controller_abstention() -> None:
    question = (
        "As of May 26, 2023, what is the total amount PepsiCo may borrow under its "
        "unsecured revolving credit agreements?"
    )

    def retrieve(request: Any, _decision: Any) -> dict[str, Any]:
        return {
            "evidence": [
                _revolving_span(str(request.retrieval_round_id), "364_day:2023-05-26")
            ]
        }

    def generate(_request: Any, _decision: Any, _bundle: Any) -> str:
        raise AssertionError("incomplete collection must not reach generation")

    result = execute_controller_turn(
        DocQARequest(
            prompt=question,
            route_policy="doc",
            verification_mode="strict",
            verification_domain="finance",
            origin="benchmark",
            query_plan=_plan(question),
        ),
        retrieve=retrieve,
        generate=generate,
    )

    assert result.retrieve_decision.status != "good"
    assert result.guardrail_decision.action == "abstain"
    assert result.answer == ABSTAIN_MESSAGE
