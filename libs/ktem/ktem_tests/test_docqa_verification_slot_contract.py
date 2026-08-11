from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan
from ktem.docqa.query_planning import (
    bind_evidence_slots,
    build_query_plan,
    missing_slot_queries,
)
from ktem.docqa.verification import (
    VerifyDecision,
    verify_decision,
    with_verification_evidence,
)


def test_verification_only_slot_reaches_claim_verification_without_false_support():
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

    assert decision.status == "unknown"
    assert decision.claims == ["The first finding reports improved accuracy."]


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


def _finance_support_request(slot: EvidenceSlot) -> DocQARequest:
    plan = QueryPlan(
        answer_type="extractive",
        question_type="long_form",
        plan_id="plan:claim-aware-support",
        evidence_slots=(slot,),
    )
    return DocQARequest(
        prompt="What drove the reduction in SG&A expense as a percent of net sales in FY2023?",
        verification_mode="strict",
        verification_domain="finance",
        query_plan=plan,
    )


def _finance_support_items() -> tuple[dict[str, str], dict[str, str]]:
    bound = {
        "evidence_id": "ranked-binding",
        "source_id": "report",
        "page_label": "2",
        "text": "SG&A expense table context.",
    }
    support = {
        "evidence_id": "claim-support",
        "source_id": "report",
        "page_label": "2",
        "text": (
            "For the full year, SG&A expenses as a percentage of net sales "
            "decreased primarily due to lower advertising spend and leverage "
            "of incentive compensation due to higher sales."
        ),
    }
    return bound, support


def test_claim_support_reconciles_to_selected_slot_compatible_evidence():
    bound, support = _finance_support_items()
    request = _finance_support_request(
        EvidenceSlot(
            slot_id="support:primary",
            role="support",
            metric="drove reduction sg expense as net sales fy2023",
            status="filled",
            evidence_ids=(identity_of(bound).key,),
        )
    )
    bundle = EvidenceBundle(route="text_rag", items=[bound, support])

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="ok"),
        bundle,
        answer=(
            "SG&A expenses as a percentage of net sales decreased primarily due "
            "to lower advertising spend and leverage of incentive compensation "
            "due to higher sales."
        ),
    )
    verified = with_verification_evidence(bundle, decision, request=request)

    assert decision.status == "supported"
    assert verified.metadata["verification_slot_states"] == [
        {
            "slot_id": "support:primary",
            "status": "verified_support",
            "evidence_ids": [identity_of(support).key],
        }
    ]


def test_claim_support_reconciliation_rejects_incompatible_selected_evidence():
    bound, support = _finance_support_items()
    request = _finance_support_request(
        EvidenceSlot(
            slot_id="support:primary",
            role="support",
            metric="net sales",
            status="filled",
            evidence_ids=(identity_of(bound).key,),
        )
    )
    bundle = EvidenceBundle(route="text_rag", items=[bound, support])

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="ok"),
        bundle,
        answer=(
            "SG&A expenses as a percentage of net sales decreased primarily due "
            "to lower advertising spend and leverage of incentive compensation "
            "due to higher sales."
        ),
    )

    assert decision.status == "unknown"
    assert decision.action == "abstain"


def test_claim_support_reconciliation_rejects_support_outside_selected_context():
    bound, support = _finance_support_items()
    request = _finance_support_request(
        EvidenceSlot(
            slot_id="support:primary",
            role="support",
            metric="drove reduction sg expense as net sales fy2023",
            status="filled",
            evidence_ids=(identity_of(bound).key,),
        )
    )
    decision = VerifyDecision(
        mode="strict",
        status="supported",
        reason="supported",
        claims=[
            "SG&A expenses as a percentage of net sales decreased primarily due "
            "to lower advertising spend and leverage of incentive compensation "
            "due to higher sales."
        ],
        verified_citations=[identity_of(support).key],
        claim_results=[
            {
                "claim_id": "claim:1",
                "claim": (
                    "SG&A expenses as a percentage of net sales decreased primarily due "
                    "to lower advertising spend and leverage of incentive compensation "
                    "due to higher sales."
                ),
                "status": "supported",
                "supporting_evidence_ids": [identity_of(support).key],
                "contradicting_evidence_ids": [],
            }
        ],
    )

    from ktem.docqa.verification import _enforce_verification_slot_support

    enforced = _enforce_verification_slot_support(
        request,
        decision,
        EvidenceBundle(route="text_rag", items=[bound]),
    )

    assert enforced.status == "unknown"
    assert enforced.action == "abstain"


def test_claim_support_reconciliation_rejects_accidental_metric_overlap():
    bound, _support = _finance_support_items()
    accidental = {
        "evidence_id": "accidental-overlap",
        "source_id": "report",
        "page_label": "2",
        "text": "Net sales percentage was reported for the year.",
    }
    request = _finance_support_request(
        EvidenceSlot(
            slot_id="support:primary",
            role="support",
            metric="drove reduction sg expense as net sales fy2023",
            status="filled",
            evidence_ids=(identity_of(bound).key,),
        )
    )
    claim = (
        "SG&A expenses as a percentage of net sales decreased primarily due "
        "to lower advertising spend and leverage of incentive compensation "
        "due to higher sales."
    )
    decision = VerifyDecision(
        mode="strict",
        status="supported",
        reason="supported",
        claims=[claim],
        verified_citations=[identity_of(accidental).key],
        claim_results=[
            {
                "claim_id": "claim:1",
                "claim": claim,
                "status": "supported",
                "supporting_evidence_ids": [identity_of(accidental).key],
                "contradicting_evidence_ids": [],
            }
        ],
    )

    from ktem.docqa.verification import _enforce_verification_slot_support

    enforced = _enforce_verification_slot_support(
        request,
        decision,
        EvidenceBundle(route="text_rag", items=[bound, accidental]),
    )

    assert enforced.status == "unknown"
    assert enforced.action == "abstain"


def test_claim_support_reconciliation_rejects_ambiguous_slot_alias():
    left = {
        "source_id": "a:b",
        "cell_id": "c",
        "text": "The report says revenue increased.",
    }
    right = {
        "source_id": "a",
        "cell_id": "b:c",
        "text": "The report says revenue increased.",
    }
    request = _finance_support_request(
        EvidenceSlot(
            slot_id="support:primary",
            role="support",
            metric="unrelated metric",
            status="filled",
            evidence_ids=(identity_of(left).legacy_key,),
        )
    )
    claim = "The report says revenue increased."
    decision = VerifyDecision(
        mode="strict",
        status="supported",
        reason="supported",
        claims=[claim],
        verified_citations=[identity_of(left).key],
        claim_results=[
            {
                "claim_id": "claim:1",
                "claim": claim,
                "status": "supported",
                "supporting_evidence_ids": [identity_of(left).key],
                "contradicting_evidence_ids": [],
            }
        ],
    )

    from ktem.docqa.verification import _enforce_verification_slot_support

    enforced = _enforce_verification_slot_support(
        request,
        decision,
        EvidenceBundle(route="text_rag", items=[left, right]),
    )

    assert enforced.status == "unknown"
    assert enforced.action == "abstain"
