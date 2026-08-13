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


def _request(*, route_policy: str, agent_mode: str | None = None) -> DocQARequest:
    return DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy=route_policy,
        allowed_routes=["doc_text", "hybrid"],
        agent_mode=agent_mode,
        selected_file_ids=["paper"],
        origin="benchmark",
    )


def _recovery_events(result: Any) -> list[dict[str, Any]]:
    return [
        event
        for event in result.controller_trace
        if event.get("verifier_recovery_attempt") == 1
    ]


def test_retrieved_unverified_text_route_rebinds_without_duplicate_retrieval() -> None:
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        return {"evidence": [_evidence("near-match", NEAR_MATCH)]}

    result = execute_controller_turn(
        _request(route_policy="doc"),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert calls == [("doc_text", 1)]
    assert result.answer == ABSTAIN_MESSAGE
    assert result.verify_decision.status == "unknown"
    events = _recovery_events(result)
    assert [event["stage"] for event in events] == [
        "evidence_rebind",
        "reverify",
    ]
    assert events[0]["slot_states_before"][0]["status"] == "retrieved_unverified"
    assert events[-1]["slot_states_after"][0]["status"] == "retrieved_unverified"
    assert events[-1]["recovered_evidence_ids"]
    assert events[-1]["stop_reason"] == "authority_recovery_exhausted"


def test_controller_auto_rebinds_before_one_bounded_route_switch() -> None:
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        text = NEAR_MATCH if decision.legacy_route == "doc_text" else EXACT_AUTHORITY
        return {"evidence": [_evidence(f"evidence-{len(calls)}", text)]}

    result = execute_controller_turn(
        _request(route_policy="auto"),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert calls == [("doc_text", 1), ("hybrid", 2)]
    assert result.answer == "yes"
    assert result.verify_decision.status == "supported"
    events = _recovery_events(result)
    assert [event["stage"] for event in events] == [
        "evidence_rebind",
        "reverify",
        "route_switch",
    ]
    transition = events[-1]
    assert transition["from_route"] == "doc_text"
    assert transition["to_route"] == "hybrid"
    assert transition["recovered_evidence_ids"]
    assert transition["slot_states_before"][0]["status"] == "retrieved_unverified"
    assert transition["slot_states_after"][0]["status"] == "verified_support"
    assert transition["stop_reason"] == "authority_recovered"


def test_thorough_recovery_keeps_full_crag_stage_sequence() -> None:
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        text = NEAR_MATCH if request.retrieval_round_id == 1 else EXACT_AUTHORITY
        return {"evidence": [_evidence(f"evidence-{len(calls)}", text)]}

    result = execute_controller_turn(
        _request(route_policy="auto", agent_mode="thorough"),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert calls == [("doc_text", 1), ("doc_text", 2)]
    events = _recovery_events(result)
    assert [event["stage"] for event in events] == [
        "critic",
        "focused_retrieval",
        "evidence_rebind",
        "reverify",
    ]
    assert all(event["agent_mode"] == "thorough" for event in events)
    assert events[0]["slot_states_before"][0]["status"] == "retrieved_unverified"
    assert events[-1]["slot_states_after"][0]["status"] == "verified_support"
    assert events[-1]["stop_reason"] == "authority_recovered"


def test_verifier_recovery_has_one_bounded_round_after_normal_round_two() -> None:
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        text = {
            1: "The paper introduces a conversational system.",
            2: NEAR_MATCH,
            3: EXACT_AUTHORITY,
        }[request.retrieval_round_id]
        return {"evidence": [_evidence(f"evidence-{len(calls)}", text)]}

    result = execute_controller_turn(
        _request(route_policy="auto"),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert calls == [
        ("doc_text", 1),
        ("doc_text", 2),
        ("hybrid", 3),
    ]
    assert result.answer == "yes"
    assert result.verify_decision.status == "supported"
    assert result.evidence_bundle.metadata["verifier_focused_retrieval_attempt"] == 1
    assert result.evidence_bundle.metadata["verifier_recovery_round"] == 3
    [transition] = [
        event for event in _recovery_events(result) if event["stage"] == "route_switch"
    ]
    assert transition["retrieval_round"] == 3
    assert transition["stop_reason"] == "authority_recovered"
