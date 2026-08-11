from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan
from ktem.docqa.query_planning import build_query_plan, missing_slot_requests
from ktem.docqa.verification import VerifyDecision, with_verification_evidence


def test_boolean_candidate_relation_mismatch_stays_missing():
    plan = build_query_plan(
        "Did the authors compare the model with the baseline?",
        answer_type="boolean",
        verification_domain="qasper",
    )
    unrelated = {
        "evidence_id": "unrelated",
        "source_id": "paper",
        "text": "We evaluated the model on clinical tasks.",
    }

    bound = bind_evidence_slots(plan, [unrelated])

    slot = next(
        slot for slot in bound.evidence_slots if slot.slot_id == "support:proposition"
    )
    assert slot.status == "missing"
    assert slot.evidence_ids == ()


def test_future_boolean_candidate_is_not_bound_as_authority():
    plan = build_query_plan(
        "Did the authors evaluate the model on clinical tasks?",
        answer_type="boolean",
        verification_domain="qasper",
    )
    future = {
        "evidence_id": "future",
        "source_id": "paper",
        "section_id": "results",
        "text": "Our future experiments will evaluate the model on clinical tasks.",
    }

    bound = bind_evidence_slots(plan, [future])

    [slot] = bound.evidence_slots
    assert slot.status == "missing"
    assert slot.evidence_ids == ()


def test_prior_work_boolean_candidate_is_retained_as_unverified_support():
    question = "Did previous work evaluate the model on clinical tasks?"
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )
    cited = {
        "evidence_id": "prior-work",
        "source_id": "paper",
        "section_id": "related_work",
        "text": "Previous work evaluated the model on clinical tasks.",
    }

    bound = bind_evidence_slots(plan, [cited])

    [slot] = bound.evidence_slots
    assert slot.status == "retrieved_unverified"
    assert slot.evidence_ids == (identity_of(cited).key,)


def test_current_paper_boolean_question_rejects_cited_work_candidate():
    question = "Did the authors evaluate the model on clinical tasks?"
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )
    cited = {
        "evidence_id": "prior-work",
        "source_id": "paper",
        "section_id": "related_work",
        "text": "Previous work evaluated the model on clinical tasks.",
    }

    bound = bind_evidence_slots(plan, [cited])

    [slot] = bound.evidence_slots
    assert slot.status == "missing"
    assert slot.evidence_ids == ()


def test_boolean_candidate_binding_keeps_only_the_matching_slot_pending():
    plan = QueryPlan(
        answer_type="boolean",
        question_type="simple_fact",
        plan_id="plan:boolean-two-slots",
        constraints={"verification_domain": "qasper"},
        evidence_slots=(
            EvidenceSlot(
                slot_id="support:evaluate",
                role="support",
                metric="authors evaluate model on clinical tasks",
                statement_kind="boolean_proposition",
                required_for_retrieval=False,
                required_for_verification=True,
                query="Did the authors evaluate the model on clinical tasks?",
            ),
            EvidenceSlot(
                slot_id="support:compare",
                role="support",
                metric="authors compare model with baseline",
                statement_kind="boolean_proposition",
                required_for_retrieval=False,
                required_for_verification=True,
                query="Did the authors compare the model with the baseline?",
            ),
        ),
    )
    candidate = {
        "evidence_id": "candidate",
        "source_id": "paper",
        "text": "We evaluated the model on clinical tasks.",
    }

    bound = bind_evidence_slots(plan, [candidate])

    assert [slot.status for slot in bound.evidence_slots] == [
        "retrieved_unverified",
        "missing",
    ]
    requests = missing_slot_requests(bound)
    assert len(requests) == 1
    assert requests[0]["query_id"] == "round2:support:compare"
    assert requests[0]["slot_id"] == "support:compare"
    assert requests[0]["query"].startswith(
        "Did the authors compare the model with the baseline?"
    )
    assert requests[0]["modality"] == "auto"


def test_exact_candidate_identity_can_promote_boolean_slot_authority():
    question = "Did the authors evaluate the model on clinical tasks?"
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )
    candidate = {
        "evidence_id": "candidate",
        "source_id": "paper",
        "text": "We evaluated the model on clinical tasks.",
    }
    bound = bind_evidence_slots(plan, [candidate])
    request = DocQARequest(
        prompt=question,
        verification_mode="strict",
        verification_domain="qasper",
        query_plan=bound,
    )
    bundle = EvidenceBundle(route="doc_text", items=[candidate])
    identity = identity_of(candidate).key
    decision = VerifyDecision(
        mode="strict",
        status="supported",
        reason="exact candidate support",
        claims=[candidate["text"]],
        verified_citations=[identity],
        claim_results=[
            {
                "claim_id": "claim:1",
                "claim": candidate["text"],
                "status": "supported",
                "supporting_evidence_ids": [identity],
            }
        ],
    )

    verified = with_verification_evidence(bundle, decision, request=request)

    [slot] = request.query_plan.evidence_slots
    assert slot.status == "verified_support"
    assert slot.evidence_ids == (identity,)
    assert verified.metadata["query_plan"]["state_authority"] == (
        "verified_claim_support.v1"
    )
