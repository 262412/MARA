from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import RetrieveDecision, VerifyDecision
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn
from ktem.docqa.execution_verification import _revise_qasper_answer_relation
from ktem.docqa.pipeline_stage_timings import PipelineStageTimings
from ktem.docqa.qasper_answer_revision import assess_qasper_answer_revision
from ktem.docqa.query_planning import ensure_request_query_plan

QUESTION = "What background knowledge do they leverage?"
RAW_ANSWER = (
    "The background knowledge they leverage includes labeled features, class "
    "distribution neutral features. Labeled features are manually provided "
    "indicators of specific classes. Class distribution can guide the model's "
    "predictions. Neutral features are common across all categories. The model "
    "also incorporates the maximum entropy principle and KL divergence."
)
DIRECT_AUTHORITY = (
    "We address the robustness problem on top of GE-FL BIBREF0, a GE method "
    "which leverages labeled features as prior knowledge."
)


def _evidence(evidence_id: str, text: str, **extra: Any) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "method",
        "text": text,
        **extra,
    }


def _request(
    route_policy: str = "doc",
    allowed_routes: list[str] | None = None,
    agent_mode: str | None = None,
) -> DocQARequest:
    return DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
        task_type="free_text",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy=route_policy,
        allowed_routes=allowed_routes or ["doc_text"],
        agent_mode=agent_mode,
        selected_file_ids=["paper"],
        origin="benchmark",
    )


def _run(
    evidence: list[dict[str, Any]],
    *,
    answer: str = RAW_ANSWER,
    request: DocQARequest | None = None,
) -> Any:
    return execute_controller_turn(
        request or _request(),
        retrieve=lambda *_args: {"evidence": evidence},
        generate=lambda *_args: answer,
    )


def _revision_events(result: Any) -> list[dict[str, Any]]:
    return [
        event
        for event in result.controller_trace
        if event.get("stage") == "answer_revision"
    ]


def test_supported_core_with_unverified_extensions_is_revised_and_freshly_verified() -> (
    None
):
    authority = _evidence("direct", DIRECT_AUTHORITY)
    authority_id = identity_of(authority).key

    result = _run([authority])

    assert result.answer == "labeled features"
    assert result.engine_terminal_answer == "labeled features"
    assert result.engine_terminal_commit["semantic_answer"] == "labeled features"
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.action == "generate"
    assert result.guardrail_decision.status == "ok"
    assert result.guardrail_decision.action == "return"
    assert result.verify_decision.claims == ["labeled features"]
    assert result.verify_decision.unknown_claims == []
    assert result.verify_decision.authoritative_evidence_id == authority_id
    assert result.verify_decision.verified_citations == [authority_id]
    assert result.verify_decision.typed_authority["state"] == "verified_support"
    assert result.verify_decision.typed_authority["candidate_answer"] == (
        "labeled features"
    )
    [slot] = result.evidence_bundle.metadata["query_plan"]["evidence_slots"]
    assert slot["slot_id"] == "support:answer_relation"
    assert slot["status"] == "verified_support"
    assert slot["evidence_ids"] == [authority_id]
    [claim] = result.verify_decision.claim_results
    [atom] = result.verify_decision.typed_authority["authority_atoms"]
    assert claim["authoritative_evidence_id"] == atom["evidence_id"] == authority_id
    assert claim["authoritative_evidence_ref"] == atom["evidence_ref"]
    assert claim["authoritative_span_id"] == atom["span_id"]
    assert claim["authoritative_quote"] == atom["quote"] == DIRECT_AUTHORITY
    assert claim["object"] == atom["object"] == "labeled features"
    [verified_item] = result.evidence_bundle.metadata["verified_claim_support_evidence"]
    assert identity_of(verified_item).key == authority_id
    [event] = _revision_events(result)
    assert "labeled features" in event["original_candidate"]
    assert "class distribution" in event["original_candidate"]
    assert "KL divergence" in event["original_candidate"]
    assert event["revised_candidate"] == "labeled features"
    assert event["authority_evidence_id"] == authority_id
    assert event["authority_evidence_ref"] == atom["evidence_ref"]
    assert event["authority_changed"] is True
    assert event["stop_reason"] == "answer_revision_verified"
    assert not any(
        event.get("stage") == "focused_retrieval" for event in result.controller_trace
    )


def test_revision_preserves_canonical_quote_offsets_in_all_authority_refs() -> None:
    canonical_start = 400
    authority = _evidence(
        "direct",
        DIRECT_AUTHORITY,
        chunk_start=canonical_start,
        chunk_end=canonical_start + len(DIRECT_AUTHORITY),
    )
    authority_id = identity_of(authority).key

    result = _run([authority])

    [atom] = result.verify_decision.typed_authority["authority_atoms"]
    expected_ref = (
        f"{authority_id}#quote:{canonical_start}:"
        f"{canonical_start + len(DIRECT_AUTHORITY)}"
    )
    assert atom["evidence_ref"] == atom["span_id"] == expected_ref
    [event] = _revision_events(result)
    assert event["authority_evidence_ref"] == event["authority_span_id"] == expected_ref


def test_revision_is_attempted_once_per_distinct_evidence_bundle() -> None:
    request = _request()
    authority = _evidence("direct", DIRECT_AUTHORITY)
    bundle = EvidenceBundle(route="doc_text", items=[authority], metadata={})
    initial = VerifyDecision(
        mode="strict",
        status="unknown",
        reason="extended claim is unsupported",
        action="revise",
        typed_authority={
            "state": "missing",
            "reason": "claim_extension_unverified",
        },
    )
    calls: list[str] = []

    def reject_fresh_verification(*_args: Any) -> VerifyDecision:
        calls.append("verify")
        return VerifyDecision(
            mode="strict",
            status="unknown",
            reason="fresh verification rejected the proposal",
            action="abstain",
            typed_authority={"state": "missing", "reason": "relation_missing"},
        )

    args = (
        request,
        RetrieveDecision("good", "evidence available"),
        bundle,
        RAW_ANSWER,
        initial,
        reject_fresh_verification,
        PipelineStageTimings(),
    )
    _, _, first_event = _revise_qasper_answer_relation(*args)
    _, _, duplicate_event = _revise_qasper_answer_relation(*args)
    changed_bundle = EvidenceBundle(
        route="doc_text",
        items=[authority, _evidence("new-topic", "Additional topic context.")],
        metadata=dict(bundle.metadata),
    )
    changed_args = (*args[:2], changed_bundle, *args[3:])
    _, _, changed_event = _revise_qasper_answer_relation(*changed_args)

    assert first_event is not None
    assert first_event["stop_reason"] == "answer_revision_verification_failed"
    assert duplicate_event is None
    assert changed_event is not None
    assert calls == ["verify", "verify"]


def test_typed_revision_assessment_records_ambiguous_direct_authorities() -> None:
    request = _request()
    initial = VerifyDecision(
        mode="strict",
        status="unknown",
        reason="extended claims are unsupported",
        action="revise",
        typed_authority={
            "state": "missing",
            "reason": "claim_extension_unverified",
        },
    )
    evidence = [
        _evidence("first", "We leverage labeled features as prior knowledge."),
        _evidence("second", "We leverage class distribution as prior knowledge."),
    ]

    assessment = assess_qasper_answer_revision(request, initial, evidence)

    assert assessment.eligible is True
    assert assessment.proposal is None
    assert assessment.reason == "direct_answer_relation_ambiguous"
    assert assessment.ambiguity_status == "multiple_direct_objects"
    assert assessment.conflict_status == "potential_conflict"
    assert assessment.candidate_evidence_ids == tuple(
        sorted(identity_of(item).key for item in evidence)
    )


@pytest.mark.parametrize("answer_type", ("evidence_qa", "qa"))
def test_revision_normalizes_qasper_free_text_answer_type_aliases(
    answer_type: str,
) -> None:
    request = _request()
    request.query_plan = replace(
        ensure_request_query_plan(request),
        answer_type=answer_type,
    )
    initial = VerifyDecision(
        mode="strict",
        status="unknown",
        reason="extended claims are unsupported",
        action="revise",
        typed_authority={
            "state": "missing",
            "reason": "claim_extension_unverified",
        },
    )

    assessment = assess_qasper_answer_revision(
        request,
        initial,
        [_evidence("direct", DIRECT_AUTHORITY)],
    )

    assert assessment.eligible is True
    assert assessment.proposal is not None
    assert assessment.proposal.revised_answer == "labeled features"


@pytest.mark.parametrize(
    "evidence",
    (
        _evidence(
            "topic-only",
            "Labeled features are useful background knowledge for classification.",
        ),
        _evidence(
            "related-work",
            "Prior work leverages labeled features as prior knowledge.",
            section_id="related_work",
        ),
    ),
    ids=("topic_only", "related_work_actor"),
)
def test_revision_requires_direct_current_paper_relation(
    evidence: dict[str, Any],
) -> None:
    result = _run([evidence])

    assert result.answer == ABSTAIN_MESSAGE
    assert result.engine_terminal_answer == "unanswerable"
    assert result.verify_decision.status == "unknown"
    assert result.verify_decision.typed_authority["state"] == "missing"
    assert result.verify_decision.verified_citations == []
    assert not any(
        event.get("stop_reason") == "answer_revision_verified"
        for event in _revision_events(result)
    )


def test_revision_abstains_when_two_direct_objects_are_equally_authoritative() -> None:
    result = _run(
        [
            _evidence("first", "We leverage labeled features as prior knowledge."),
            _evidence("second", "We leverage class distribution as prior knowledge."),
        ]
    )

    assert result.answer == ABSTAIN_MESSAGE
    assert result.engine_terminal_answer == "unanswerable"
    assert result.verify_decision.status == "unknown"
    assert result.verify_decision.typed_authority["state"] == "missing"
    assert result.verify_decision.verified_citations == []
    assert not any(
        event.get("stop_reason") == "answer_revision_verified"
        for event in _revision_events(result)
    )


def test_failed_revision_does_not_retain_old_supported_authority() -> None:
    result = _run(
        [
            _evidence("first", DIRECT_AUTHORITY),
            _evidence(
                "second",
                "We leverage class distribution as prior knowledge.",
            ),
        ],
        answer=(
            "The authors leverage labeled features. The authors also leverage "
            "an unsupported private ontology."
        ),
    )

    assert result.verify_decision.status == "unknown"
    assert result.verify_decision.verified_citations == []
    assert result.verify_decision.authoritative_evidence_id == ""
    assert all(
        claim.get("authority_status") == "missing"
        and claim.get("supporting_evidence_ids") == []
        for claim in result.verify_decision.claim_results
    )


@pytest.mark.parametrize(
    ("route_policy", "allowed_routes", "agent_mode", "route_id"),
    (
        ("doc", ["doc_text"], None, "text_rag"),
        ("auto", ["doc_text", "hybrid"], None, "controller_auto"),
        ("auto", ["doc_text", "hybrid"], "thorough", "crag_guarded"),
    ),
)
def test_answer_revision_contract_is_route_invariant(
    route_policy: str,
    allowed_routes: list[str],
    agent_mode: str | None,
    route_id: str,
) -> None:
    authority = _evidence("direct", DIRECT_AUTHORITY)
    result = _run(
        [authority],
        request=_request(route_policy, allowed_routes, agent_mode),
    )

    assert result.answer == "labeled features", route_id
    [event] = _revision_events(result)
    assert event["contract_id"] == "qasper_answer_revision.v1"
    if route_id == "crag_guarded":
        assert agent_mode == "thorough"


def test_boolean_conflict_does_not_enter_free_text_answer_revision() -> None:
    question = "Did the authors release the code?"
    request = DocQARequest(
        prompt=question,
        retrieval_query=question,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        origin="benchmark",
    )
    result = execute_controller_turn(
        request,
        retrieve=lambda *_args: {
            "evidence": [
                _evidence("yes", "We released the code publicly."),
                _evidence("no", "We did not release the code publicly."),
            ]
        },
        generate=lambda *_args: "no",
    )

    assert _revision_events(result) == []
