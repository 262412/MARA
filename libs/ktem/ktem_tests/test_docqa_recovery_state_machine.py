from __future__ import annotations

from time import monotonic
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


def test_retrieved_unverified_text_route_runs_one_targeted_retrieval_after_rebind() -> (
    None
):
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        return {"evidence": [_evidence("near-match", NEAR_MATCH)]}

    result = execute_controller_turn(
        _request(route_policy="doc"),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert calls == [("doc_text", 1), ("doc_text", 2)]
    assert result.answer == ABSTAIN_MESSAGE
    assert result.verify_decision.status == "unknown"
    events = _recovery_events(result)
    assert [event["stage"] for event in events] == [
        "evidence_rebind",
        "focused_retrieval",
        "evidence_rebind",
    ]
    assert events[0]["slot_states_before"][0]["status"] == "retrieved_unverified"
    assert events[-1]["slot_states_after"][0]["status"] == "retrieved_unverified"
    assert events[-1]["recovered_evidence_ids"]
    assert events[-1]["stop_reason"] == "recovery_no_progress"
    assert events[-1]["authority_changed"] is False


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
        "route_switch",
        "reverify",
    ]
    transition = events[-2]
    assert transition["from_route"] == "doc_text"
    assert transition["to_route"] == "hybrid"
    assert transition["recovered_evidence_ids"]
    assert transition["slot_states_before"][0]["status"] == "retrieved_unverified"
    assert transition["slot_states_after"][0]["status"] == "verified_support"
    assert transition["authority_changed"] is True
    assert transition["authority_state_after"] == "verified_support"
    assert transition["expected_authority_gain"] is True
    assert events[-1]["stop_reason"] == "authority_recovered"


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
    assert events[-1]["authority_changed"] is True
    assert events[-1]["authority_state_after"] == "verified_support"
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
    [terminal] = [
        event for event in _recovery_events(result) if event["stage"] == "reverify"
    ]
    assert terminal["stop_reason"] == "authority_recovered"


def test_identical_recovery_evidence_stops_without_identical_reverification() -> None:
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        return {"evidence": [_evidence("same", NEAR_MATCH)]}

    result = execute_controller_turn(
        _request(route_policy="doc"),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert calls == [("doc_text", 1), ("doc_text", 2)]
    recovery = _recovery_events(result)
    assert not [event for event in recovery if event["stage"] == "reverify"]
    terminal = recovery[-1]
    assert terminal["stop_reason"] == "recovery_no_progress"
    assert terminal["new_evidence_ids"] == []
    assert terminal["removed_evidence_ids"] == []
    assert terminal["candidate_changed"] is False
    assert terminal["proposition_binding_changed"] is False
    assert terminal["authority_changed"] is False
    assert terminal["recovery_action"] == "stop_without_reverify"


def test_focused_recovery_trace_records_typed_frame_and_budget() -> None:
    def retrieve(request: DocQARequest, _decision: Any) -> dict[str, Any]:
        text = NEAR_MATCH if request.retrieval_round_id == 1 else EXACT_AUTHORITY
        return {"evidence": [_evidence(f"round-{request.retrieval_round_id}", text)]}

    request = _request(route_policy="doc")
    request.route_deadline_monotonic = monotonic() + 30.0
    result = execute_controller_turn(
        request,
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    [focused] = [
        event
        for event in _recovery_events(result)
        if event["stage"] == "focused_retrieval"
    ]
    assert focused["recovery_frame"]["actor"] == "current_paper"
    assert focused["recovery_frame"]["predicate"] == "evaluate"
    assert focused["recovery_frame"]["object"] == "dataset"
    assert focused["remaining_route_seconds"] > 0
    assert focused["recovery_action"] == "targeted_retrieval"


def test_insufficient_budget_skips_optional_verifier_recovery() -> None:
    calls: list[int] = []

    def retrieve(request: DocQARequest, _decision: Any) -> dict[str, Any]:
        calls.append(request.retrieval_round_id)
        return {"evidence": [_evidence("near-match", NEAR_MATCH)]}

    request = _request(route_policy="doc")
    request.route_deadline_monotonic = monotonic() + 1.0
    request.route_terminal_reserve_seconds = 0.0
    result = execute_controller_turn(
        request,
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert calls == [1]
    [skipped] = [
        event
        for event in result.controller_trace
        if event.get("stage") == "verifier_recovery"
    ]
    assert skipped["recovery_action"] == "skip_optional_recovery"
    assert skipped["stop_reason"] == "insufficient_remaining_time"
    assert 0 < skipped["remaining_route_seconds"] <= 1.0


def test_missing_required_slot_records_concrete_bounded_stop_reason() -> None:
    result = execute_controller_turn(
        _request(route_policy="doc"),
        retrieve=lambda *_args: {
            "evidence": [
                _evidence("irrelevant", "The paper introduces a dialogue system.")
            ]
        },
        generate=lambda *_args: "yes",
    )

    assert result.retrieve_decision.status == "poor"
    assert result.retrieve_decision.retry is False
    assert "recovery_no_progress" in result.retrieve_decision.reason
    stops = [
        event
        for event in result.controller_trace
        if event.get("stop_reason")
        in {
            "max_retrieval_rounds_exhausted",
            "recovery_no_progress",
            "route_switch_candidates_exhausted",
        }
    ]
    assert stops
    assert result.evidence_bundle.metadata["missing_required_slot_ids"] == [
        "support:boolean_proposition"
    ]


def test_missing_boolean_slot_uses_natural_language_recovery_query_and_records_delta() -> (
    None
):
    calls: list[tuple[int, str, dict[str, Any]]] = []
    request = _request(route_policy="doc")
    request.allowed_routes = ["doc_text"]

    def retrieve(request: DocQARequest, _decision: Any) -> dict[str, Any]:
        calls.append(
            (
                request.retrieval_round_id,
                request.retrieval_query,
                dict(getattr(request, "retrieval_query_metadata", {}) or {}),
            )
        )
        return {
            "evidence": [
                _evidence(
                    f"irrelevant-{request.retrieval_round_id}",
                    "The paper introduces a dialogue system.",
                )
            ]
        }

    result = execute_controller_turn(
        request,
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert [round_id for round_id, _query, _metadata in calls] == [1, 2]
    assert calls[0][1] == QUESTION
    assert calls[0][2] == {
        "contract_id": "initial_retrieval_query.v1",
        "query_kind": "initial",
    }
    second_query = calls[-1][1]
    assert second_query.count(QUESTION) == 1
    assert second_query != QUESTION
    assert all(
        token not in second_query
        for token in ("actor:", "predicate:", "object:", "object_role:")
    )
    assert calls[-1][2]["contract_id"] == "recovery_query.v1"
    assert calls[-1][2]["query_kind"] == "recovery"
    assert calls[-1][2]["typed_frame"] == {
        "actor": "current_paper",
        "predicate": "evaluate",
        "object": "dataset",
        "object_role": "proposition_object",
        "qualifier": "none",
        "quantifier": "none",
        "scope": "document",
    }
    [recovery] = [
        event
        for event in result.controller_trace
        if event.get("stage") == "targeted_retrieval"
    ]
    assert recovery["failure_type"] == "required_boolean_authority_missing"
    assert recovery["recovery_action"] == "targeted_slot_retrieval"
    assert recovery["slot_states_before"][0]["status"] == "missing"
    assert recovery["slot_states_after"][0]["status"] == "missing"
    assert recovery["stop_reason"] == "recovery_no_progress"
    assert recovery["new_semantic_evidence_ids"] == []


def test_qasper_first_round_uses_the_original_question_once() -> None:
    calls: list[tuple[int, str, dict[str, Any]]] = []
    request = _request(route_policy="doc")
    request.allowed_routes = ["doc_text"]

    def retrieve(request: DocQARequest, _decision: Any) -> dict[str, Any]:
        calls.append(
            (
                request.retrieval_round_id,
                request.retrieval_query,
                dict(getattr(request, "retrieval_query_metadata", {}) or {}),
            )
        )
        text = EXACT_AUTHORITY if request.retrieval_query == QUESTION else NEAR_MATCH
        return {"evidence": [_evidence(f"round-{len(calls)}", text)]}

    result = execute_controller_turn(
        request,
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert len(calls) == 1
    assert calls[0][0] == 1
    assert calls[0][1] == QUESTION
    assert calls[0][1].count(QUESTION) == 1
    assert all(
        token not in calls[0][1]
        for token in ("actor:", "predicate:", "object:", "object_role:")
    )
    assert calls[0][2] == {
        "contract_id": "initial_retrieval_query.v1",
        "query_kind": "initial",
    }
    assert result.verify_decision.status == "supported"
