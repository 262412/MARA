from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan
from ktem.docqa.query_planning import (
    bind_evidence_slots,
    build_query_plan,
    missing_slot_queries,
)
from ktem.docqa.verification import verify_decision, with_verification_evidence


def test_required_verification_slot_blocks_supported_status():
    plan = QueryPlan(
        answer_type="free_text",
        question_type="cross_page",
        plan_id="plan:verification-slot",
        evidence_slots=(
            EvidenceSlot(
                slot_id="support:left",
                role="support",
                status="filled",
                evidence_ids=("evidence:paper:left",),
            ),
            EvidenceSlot(
                slot_id="support:right",
                role="support",
                required_for_retrieval=False,
                required_for_verification=True,
                status="missing",
            ),
        ),
    )
    request = DocQARequest(
        prompt="Compare the two findings.",
        verification_mode="strict",
        query_plan=plan,
    )
    bundle = EvidenceBundle(
        route="doc_text",
        items=[
            {
                "evidence_id": "left",
                "source_id": "paper",
                "text": "The first finding reports improved accuracy.",
            }
        ],
    )

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="ok"),
        bundle,
        answer="The first finding reports improved accuracy.",
    )

    assert decision.status == "not_enough_evidence"
    assert decision.action == "abstain"
    assert "support:right" in decision.reason


def test_boolean_verifier_checks_proposition_polarity():
    plan = QueryPlan(
        answer_type="boolean",
        question_type="simple_fact",
        plan_id="plan:boolean",
        evidence_slots=(
            EvidenceSlot(
                slot_id="support:boolean_proposition",
                role="support",
                status="filled",
                evidence_ids=("evidence:paper:result",),
            ),
        ),
    )
    request = DocQARequest(
        prompt="Does the proposed model outperform the baseline?",
        verification_mode="strict",
        query_plan=plan,
    )
    bundle = EvidenceBundle(
        route="doc_text",
        items=[
            {
                "evidence_id": "result",
                "source_id": "paper",
                "text": "The proposed model does not outperform the baseline.",
            }
        ],
    )

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="ok"),
        bundle,
        answer="yes",
    )

    assert decision.status == "unsupported"
    assert decision.claim_results[0]["status"] == "contradicted"


def test_retrieved_unverified_boolean_slot_can_reach_typed_verification():
    evidence = {
        "evidence_id": "result",
        "source_id": "paper",
        "text": "The proposed model outperforms the baseline on every task.",
    }
    plan = QueryPlan(
        answer_type="boolean",
        question_type="simple_fact",
        plan_id="plan:boolean-retrieved",
        evidence_slots=(
            EvidenceSlot(
                slot_id="support:boolean_proposition",
                role="support",
                statement_kind="boolean_proposition",
                required_for_retrieval=False,
                required_for_verification=True,
                status="retrieved_unverified",
                evidence_ids=("evidence:paper:result",),
            ),
        ),
    )
    request = DocQARequest(
        prompt="Does the proposed model outperform the baseline?",
        verification_mode="strict",
        verification_domain="qasper",
        query_plan=plan,
    )
    bundle = EvidenceBundle(route="doc_text", items=[evidence])

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="ok"),
        bundle,
        answer="yes",
    )
    verified = with_verification_evidence(bundle, decision, request=request)

    assert decision.status == "supported"
    assert verified.metadata["verification_slot_states"] == [
        {
            "slot_id": "support:boolean_proposition",
            "status": "verified_support",
            "evidence_ids": ["evidence:paper:result"],
        }
    ]


def test_boolean_proposition_binding_is_retrieved_but_unverified():
    plan = build_query_plan(
        "Does the proposed model outperform the baseline?",
        answer_type="boolean",
        verification_domain="qasper",
    )
    bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "result",
                "source_id": "paper",
                "text": "The proposed model outperforms the baseline on every task.",
            }
        ],
    )

    [slot] = bound.evidence_slots
    assert slot.status == "retrieved_unverified"
    assert slot.evidence_ids == ("evidence:paper:result",)
    assert missing_slot_queries(bound) == []


def test_finance_execution_slots_remain_retrieval_hard_gates():
    plan = build_query_plan(
        "What was the percentage change in revenue from 2021 to 2022?",
        answer_type="numeric",
        verification_domain="finance",
    )

    assert all(slot.required_for_retrieval for slot in plan.evidence_slots)
    assert all(slot.required_for_execution for slot in plan.evidence_slots)
    assert missing_slot_queries(plan) == [
        "revenue consolidated statements of income 2021",
        "revenue consolidated statements of income 2022",
    ]
