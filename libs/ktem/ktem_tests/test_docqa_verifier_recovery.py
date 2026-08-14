from __future__ import annotations

from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn

QUESTION = "Do the authors conduct experiments on the dataset?"
NEAR_MATCH = "The dataset provides experiments for evaluation."
EXACT_AUTHORITY = "We conduct experiments on the dataset and report the results."


def _evidence(evidence_id: str, text: str) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "experiments",
        "text": text,
    }


def _request(
    *,
    route_policy: str,
    allowed_routes: list[str],
    agent_mode: str | None = None,
) -> DocQARequest:
    return DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy=route_policy,
        allowed_routes=allowed_routes,
        agent_mode=agent_mode,
        selected_file_ids=["paper"],
        origin="benchmark",
    )


def _stage_events(result: Any, stage: str) -> list[dict[str, Any]]:
    return [event for event in result.controller_trace if event.get("stage") == stage]


def test_text_rag_runs_one_focused_retrieval_when_rebind_does_not_improve_authority():
    calls: list[tuple[str, int, str]] = []
    generation_calls = 0

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append(
            (
                decision.legacy_route,
                request.retrieval_round_id,
                request.retrieval_query,
            )
        )
        return {"evidence": [_evidence(f"evidence-{len(calls)}", NEAR_MATCH)]}

    def generate(*_args: Any) -> str:
        nonlocal generation_calls
        generation_calls += 1
        return "yes"

    result = execute_controller_turn(
        _request(route_policy="doc", allowed_routes=["doc_text"]),
        retrieve=retrieve,
        generate=generate,
    )

    assert [(route, round_id) for route, round_id, _query in calls] == [
        ("doc_text", 1),
        ("doc_text", 2),
    ]
    assert result.answer == ABSTAIN_MESSAGE
    assert generation_calls == 1
    assert result.verify_decision.status == "unknown"
    rebinds = _stage_events(result, "evidence_rebind")
    assert not _stage_events(result, "reverify")
    rebind = rebinds[-1]
    assert rebind["retry_reason"] == "required_boolean_authority_missing"
    assert rebind["stop_reason"] == "recovery_no_progress"
    assert rebind["authority_changed"] is False
    assert rebinds[0]["slot_states_before"][0]["status"] == "retrieved_unverified"
    assert not _stage_events(result, "route_switch")


def test_controller_auto_rebinds_before_bounded_route_switch():
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        text = NEAR_MATCH if request.retrieval_round_id == 1 else EXACT_AUTHORITY
        return {"evidence": [_evidence(f"evidence-{len(calls)}", text)]}

    result = execute_controller_turn(
        _request(
            route_policy="auto",
            allowed_routes=["doc_text", "hybrid"],
        ),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert calls == [("doc_text", 1), ("hybrid", 2)]
    assert result.answer == "yes"
    assert result.controller_decision.legacy_route == "hybrid"
    [recovery] = _stage_events(result, "reverify")
    assert recovery["verifier_recovery_attempt"] == 1
    assert recovery["retry_reason"] == "required_boolean_authority_missing"
    assert recovery["stop_reason"] == "authority_recovered"
    [transition] = _stage_events(result, "route_switch")
    assert transition["authority_state_after"] == "verified_support"


def test_controller_auto_switches_route_when_no_relevant_proposition_exists():
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        text = (
            "The paper introduces a conversational system."
            if decision.legacy_route == "doc_text"
            else EXACT_AUTHORITY
        )
        return {"evidence": [_evidence(f"evidence-{len(calls)}", text)]}

    result = execute_controller_turn(
        _request(
            route_policy="auto",
            allowed_routes=["doc_text", "hybrid"],
        ),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert calls == [("doc_text", 1), ("doc_text", 2), ("hybrid", 1)]
    assert result.answer == "yes"
    [transition] = _stage_events(result, "route_switch")
    assert transition["from_route"] == "doc_text"
    assert transition["to_route"] == "hybrid"
    assert transition["failure_type"] == "retrieval_adequacy_failure"
    assert transition["recovered_evidence_ids"]
    assert transition["reverification_status"] == "supported"
    assert transition["reverification_evidence_ids"]


def test_crag_guarded_records_critic_retrieval_rebind_and_reverify_once():
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        text = NEAR_MATCH if request.retrieval_round_id == 1 else EXACT_AUTHORITY
        return {"evidence": [_evidence(f"evidence-{len(calls)}", text)]}

    result = execute_controller_turn(
        _request(
            route_policy="auto",
            allowed_routes=["doc_text", "hybrid"],
            agent_mode="thorough",
        ),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert calls == [("doc_text", 1), ("doc_text", 2)]
    recovery_stages = [
        event.get("stage")
        for event in result.controller_trace
        if event.get("verifier_recovery_attempt") == 1
    ]
    assert recovery_stages == [
        "critic",
        "focused_retrieval",
        "evidence_rebind",
        "reverify",
    ]
    assert result.answer == "yes"
    assert result.verify_decision.status == "supported"
    assert not _stage_events(result, "route_switch")


def test_verifier_recovery_exhausts_after_one_attempt_and_safely_abstains():
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        return {"evidence": [_evidence(f"evidence-{len(calls)}", NEAR_MATCH)]}

    result = execute_controller_turn(
        _request(route_policy="doc", allowed_routes=["doc_text"]),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert calls == [("doc_text", 1), ("doc_text", 2)]
    assert result.answer == ABSTAIN_MESSAGE
    assert result.verify_decision.status == "unknown"
    assert not _stage_events(result, "reverify")
    event = _stage_events(result, "evidence_rebind")[-1]
    assert event["stop_reason"] == "recovery_no_progress"
    assert event["recovery_action"] == "stop_without_reverify"
