from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan
from ktem.docqa.verification import verify_decision


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
