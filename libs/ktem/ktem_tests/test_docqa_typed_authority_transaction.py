from __future__ import annotations

from dataclasses import replace

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.typed_proposition_authority_atoms import exact_boolean_atom
from ktem.docqa.verification import verify_decision, with_verification_evidence
from ktem.docqa.verification_schema import VerifyDecision
from ktem.docqa.verification_slot_support import enforce_verification_slot_support


def _item(evidence_id: str, text: str, **extra: object) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "results",
        "text": text,
        **extra,
    }


def _qasper_request(question: str, plan: QueryPlan) -> DocQARequest:
    return DocQARequest(
        prompt=question,
        task_type=plan.answer_type,
        verification_mode="strict",
        verification_domain="qasper",
        query_plan=plan,
        query_plan_state_version=1,
    )


def test_exact_boolean_authority_atomically_replaces_provisional_slot_binding() -> None:
    question = "Did the authors evaluate the model on clinical tasks?"
    unrelated = _item("unrelated", "Clinical tasks are discussed as future work.")
    authoritative = _item(
        "authoritative",
        "We evaluated the model on clinical tasks.",
        canonical_start=100,
    )
    unrelated_id = identity_of(unrelated).key
    authoritative_id = identity_of(authoritative).key
    plan = QueryPlan(
        answer_type="boolean",
        question_type="simple_fact",
        plan_id="plan:typed-transaction",
        evidence_slots=(
            EvidenceSlot(
                slot_id="support:boolean_proposition",
                role="support",
                metric=question,
                statement_kind="boolean_proposition",
                required_for_retrieval=False,
                required_for_verification=True,
                status="retrieved_unverified",
                evidence_ids=(unrelated_id,),
            ),
        ),
    )
    request = _qasper_request(question, plan)
    bundle = EvidenceBundle(route="doc_text", items=[unrelated, authoritative])

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "Yes. The authors evaluated the model on clinical tasks.",
    )
    projected = with_verification_evidence(bundle, decision, request)

    assert decision.status == "supported"
    assert decision.action == "generate"
    assert decision.authoritative_evidence_id == authoritative_id
    assert decision.verified_support_slot_ids == ["support:boolean_proposition"]
    assert decision.typed_authority["contract_id"] == ("typed_proposition_authority.v1")
    assert decision.typed_authority["state"] == "verified_support"
    [claim] = decision.claim_results
    assert claim["status"] == "supported"
    assert claim["authority_status"] == "exact"
    assert claim["verified_slot_state"] == "verified_support"
    [slot] = request.query_plan.evidence_slots
    assert slot.status == "verified_support"
    assert slot.evidence_ids == (authoritative_id,)
    assert projected.metadata["typed_authority"] == decision.typed_authority


def test_boolean_authority_atom_requires_explicit_canonical_polarity() -> None:
    question = "Did the authors evaluate the model on clinical tasks?"
    evidence = _item(
        "authoritative",
        "We evaluated the model on clinical tasks.",
    )
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )
    request = _qasper_request(question, plan)
    bundle = EvidenceBundle(route="doc_text", items=[evidence])
    verified = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "yes",
    )
    missing_polarity = replace(
        verified,
        canonical_answer_polarity="",
        claim_results=[
            {**result, "canonical_answer_polarity": ""}
            for result in verified.claim_results
        ],
    )

    assert exact_boolean_atom(missing_polarity, bundle, question=question) is None


def test_failed_authority_binding_clears_exact_claim_and_citations() -> None:
    question = "Did the authors evaluate the model on clinical tasks?"
    selected = _item("selected", "Clinical tasks are discussed as future work.")
    selected_id = identity_of(selected).key
    plan = QueryPlan(
        answer_type="boolean",
        question_type="simple_fact",
        plan_id="plan:coherent-failure",
        evidence_slots=(
            EvidenceSlot(
                slot_id="support:boolean_proposition",
                role="support",
                metric=question,
                statement_kind="boolean_proposition",
                required_for_retrieval=False,
                required_for_verification=True,
                status="retrieved_unverified",
                evidence_ids=(selected_id,),
            ),
        ),
    )
    request = _qasper_request(question, plan)
    stale = VerifyDecision(
        mode="strict",
        status="supported",
        reason="stale exact claim",
        claims=[question],
        verified_citations=["missing-authority"],
        canonical_answer_polarity="yes",
        boolean_authority_status="exact",
        authoritative_evidence_id="missing-authority",
        authoritative_evidence_ref="missing-authority#quote:0:5",
        authoritative_quote="bogus",
        actor="current_paper",
        section_scope="results",
        relation="evaluate",
        object="model clinical tasks",
        qualifier="none",
        quantifier="none",
        claim_results=[
            {
                "claim_id": "claim:1",
                "claim": question,
                "status": "supported",
                "authority_status": "exact",
                "supporting_evidence_ids": ["missing-authority"],
                "authoritative_evidence_id": "missing-authority",
                "authoritative_evidence_ref": "missing-authority#quote:0:5",
                "authoritative_quote": "bogus",
                "actor": "current_paper",
                "predicate": "evaluate",
                "arguments": ["model clinical tasks"],
                "polarity": "yes",
                "qualifier": "none",
                "quantifier": "none",
                "scope": "results",
            }
        ],
    )

    coherent = enforce_verification_slot_support(
        request,
        stale,
        EvidenceBundle(route="doc_text", items=[selected]),
        prompt=question,
        domain="qasper",
    )

    assert coherent.status == "unknown"
    assert coherent.action == "abstain"
    assert coherent.verified_citations == []
    assert coherent.canonical_answer_polarity == ""
    assert coherent.authoritative_evidence_id == ""
    [claim] = coherent.claim_results
    assert claim["status"] == "unknown"
    assert claim["authority_status"] == "missing"
    assert claim["supporting_evidence_ids"] == []


def test_qasper_free_text_plan_requires_answer_relation_authority() -> None:
    question = "How many participants did the authors recruit for the study?"
    plan = build_query_plan(
        question,
        answer_type="free_text",
        verification_domain="qasper",
    )

    [slot] = plan.evidence_slots
    assert slot.slot_id == "support:answer_relation"
    assert slot.statement_kind == "answer_relation"
    assert slot.required_for_retrieval is False
    assert slot.required_for_verification is True


def test_verification_only_slot_forwards_candidates_without_prejudging_authority() -> (
    None
):
    question = "Did the authors evaluate the model on clinical tasks?"
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )
    candidate = _item(
        "candidate",
        "We evaluated the model on clinical tasks.",
    )

    bound = bind_evidence_slots(plan, [candidate])

    [slot] = bound.evidence_slots
    assert slot.status == "retrieved_unverified"
    assert slot.evidence_ids == (identity_of(candidate).key,)


def test_qasper_free_text_topic_overlap_does_not_answer_quantity_relation() -> None:
    question = "How many participants did the authors recruit for the study?"
    plan = build_query_plan(
        question,
        answer_type="free_text",
        verification_domain="qasper",
    )
    evidence = _item(
        "topic-only",
        "The study investigated participant demographics and recruitment methods.",
    )
    request = _qasper_request(question, plan)

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=[evidence]),
        "The study investigated participant demographics and recruitment methods.",
    )

    assert decision.status == "unknown"
    assert decision.action == "abstain"
    assert decision.verified_citations == []
    assert decision.typed_authority["state"] == "missing"
    assert decision.typed_authority["reason"] == "quantity_answer_missing"
    assert all(result["status"] == "unknown" for result in decision.claim_results)


def test_qasper_definition_typo_still_requires_explicit_definition_relation() -> None:
    question = "What does the symbol repe" "sent?"
    plan = build_query_plan(
        question,
        answer_type="free_text",
        verification_domain="qasper",
    )
    evidence = _item(
        "topic-only",
        "We use the symbol while estimating a state from the observations.",
    )
    request = _qasper_request(question, plan)

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=[evidence]),
        "The symbol represents a state.",
    )

    assert decision.status == "unknown"
    assert decision.typed_authority["state"] == "missing"
    assert decision.authoritative_evidence_id == ""


def test_qasper_free_text_quantity_commits_exact_local_span() -> None:
    question = "How many participants did the authors recruit for the study?"
    plan = build_query_plan(
        question,
        answer_type="free_text",
        verification_domain="qasper",
    )
    evidence = _item(
        "participants",
        "We recruited 42 participants for the study. The cohort was then analysed.",
        canonical_start=500,
    )
    evidence_id = identity_of(evidence).key
    request = _qasper_request(question, plan)

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=[evidence]),
        "The authors recruited 42 participants.",
    )

    assert decision.status == "supported"
    assert decision.authoritative_evidence_id == evidence_id
    assert decision.authoritative_quote == "We recruited 42 participants for the study."
    assert decision.quantifier == "42"
    assert decision.typed_authority["state"] == "verified_support"
    [slot] = request.query_plan.evidence_slots
    assert slot.status == "verified_support"
    assert slot.evidence_ids == (evidence_id,)


def test_qasper_free_text_qualifier_cannot_be_filled_from_answer() -> None:
    question = "How many participants did the authors recruit for the study?"
    plan = build_query_plan(
        question,
        answer_type="free_text",
        verification_domain="qasper",
    )
    evidence = _item(
        "participants",
        "We recruited 42 participants for the study.",
    )
    request = _qasper_request(question, plan)

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=[evidence]),
        "The authors recruited at least 42 participants.",
    )

    assert decision.status == "unknown"
    assert decision.typed_authority["state"] == "missing"
    assert decision.authoritative_evidence_id == ""


def test_qasper_free_text_current_paper_scope_rejects_related_work() -> None:
    question = "What encoding method do the authors use for tokens?"
    plan = build_query_plan(
        question,
        answer_type="free_text",
        verification_domain="qasper",
    )
    evidence = _item(
        "related-method",
        "Prior work uses byte-pair encoding for tokens.",
        section_id="related_work",
    )
    request = _qasper_request(question, plan)

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=[evidence]),
        "The authors use byte-pair encoding for tokens.",
    )

    assert decision.status == "unknown"
    assert decision.typed_authority["state"] == "missing"
    assert decision.authoritative_evidence_id == ""


def test_qasper_free_text_title_only_cannot_become_authority() -> None:
    question = "How many participants did the authors recruit for the study?"
    plan = build_query_plan(
        question,
        answer_type="free_text",
        verification_domain="qasper",
    )
    title = _item(
        "title",
        "Study of 42 recruited participants",
        element_type="title",
        section_id="title",
    )
    request = _qasper_request(question, plan)

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=[title]),
        "The authors recruited 42 participants.",
    )

    assert decision.status == "unknown"
    assert decision.typed_authority["state"] == "missing"
    assert decision.authoritative_evidence_id == ""


def test_qasper_free_text_markdown_heading_cannot_become_authority() -> None:
    question = "How many participants did the authors recruit for the study?"
    plan = build_query_plan(
        question,
        answer_type="free_text",
        verification_domain="qasper",
    )
    heading = _item(
        "heading",
        "# We recruited 42 participants for the study",
    )
    request = _qasper_request(question, plan)

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=[heading]),
        "The authors recruited 42 participants.",
    )

    assert decision.status == "unknown"
    assert decision.typed_authority["state"] == "missing"
    assert decision.authoritative_evidence_id == ""


def test_boolean_actor_unknown_cannot_become_exact_authority() -> None:
    question = "Does the paper explore extraction from electronic health records?"
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )
    evidence = _item(
        "topic",
        (
            "BioIE systems aim to extract information from electronic health "
            "records for clinicians and researchers."
        ),
        section_id="introduction",
    )
    request = _qasper_request(question, plan)

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=[evidence]),
        "Yes. The paper explores extraction from electronic health records.",
    )

    assert decision.status == "unknown"
    assert decision.action == "abstain"
    assert decision.typed_authority["state"] == "missing"
    assert decision.authoritative_evidence_id == ""
    assert all(
        result.get("authority_status") != "exact" for result in decision.claim_results
    )


def test_boolean_title_only_cannot_become_exact_authority() -> None:
    question = "Did the paper assess BERT's syntactic abilities?"
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )
    title = _item(
        "paper-title",
        "Assessing BERT's Syntactic Abilities",
        element_type="title",
        section_id="title",
    )
    request = _qasper_request(question, plan)

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=[title]),
        "Yes. The paper assessed BERT's syntactic abilities.",
    )

    assert decision.status == "unknown"
    assert decision.action == "abstain"
    assert decision.typed_authority["state"] == "missing"
    assert decision.authoritative_evidence_id == ""


def test_equivalent_answer_relation_candidates_are_order_independent() -> None:
    question = "How many participants did the authors recruit for the study?"
    first = _item("z-candidate", "We recruited 42 participants for the study.")
    second = _item("a-candidate", "We recruited 42 participants for the study.")

    selected: list[tuple[str, str]] = []
    for evidence in ([first, second], [second, first]):
        plan = build_query_plan(
            question,
            answer_type="free_text",
            verification_domain="qasper",
        )
        request = _qasper_request(question, plan)
        decision = verify_decision(
            request,
            RetrieveDecision(status="good", reason="retrieved"),
            EvidenceBundle(route="doc_text", items=evidence),
            "The authors recruited 42 participants.",
        )
        selected.append(
            (
                decision.authoritative_evidence_id,
                decision.authoritative_evidence_ref,
            )
        )

    assert selected[0] == selected[1]
    assert selected[0][0] == identity_of(second).key


def test_repeating_authority_commit_is_idempotent() -> None:
    question = "How many participants did the authors recruit for the study?"
    plan = build_query_plan(
        question,
        answer_type="free_text",
        verification_domain="qasper",
    )
    evidence = _item("participants", "We recruited 42 participants for the study.")
    request = _qasper_request(question, plan)
    bundle = EvidenceBundle(route="doc_text", items=[evidence])

    first = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "The authors recruited 42 participants.",
    )
    first_version = request.query_plan_state_version
    second = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "The authors recruited 42 participants.",
    )

    assert first.status == second.status == "supported"
    assert request.query_plan_state_version == first_version
    assert first.typed_authority == second.typed_authority
