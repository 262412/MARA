from __future__ import annotations

from typing import Any

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn

QUESTION = "Did the authors use the dataset?"
# Retrieval can find this lexical context, but the verifier must not treat a
# sentence that merely discusses use as an exact Boolean proposition.
MISSING_AUTHORITY = "The paper discusses use of the dataset."
POSITIVE_AUTHORITY = "The authors use the dataset."
NEGATIVE_AUTHORITY = "The authors do not use the dataset."


def _evidence(evidence_id: str, text: str) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "page_label": "2" if "negative" in evidence_id else "1",
        "section_id": "results",
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


def _stage_events(result: Any, *stages: str) -> list[dict[str, Any]]:
    expected = set(stages)
    return [
        event for event in result.controller_trace if event.get("stage") in expected
    ]


def _terminal_events(result: Any) -> list[dict[str, Any]]:
    return [event for event in result.controller_trace if event.get("stop_reason")]


def _authority_ids(value: Any) -> set[str]:
    if isinstance(value, dict):
        values = value.values()
    else:
        values = value
    assert values
    return {
        str(authority["evidence_id"])
        for authority in values
        if isinstance(authority, dict) and authority.get("evidence_id")
    }


def _assert_authoritative_conflict(result: Any) -> dict[str, Any]:
    verify = result.verify_decision.as_dict()
    assert verify["status"] == "verified_conflict"
    assert verify["action"] == "abstain"
    assert verify["reason"] == "authoritative_conflict_abstention"
    assert verify["canonical_answer_polarity"] == ""
    assert verify["boolean_authority_status"] == "verified_conflict"

    conflict = verify["authoritative_conflict"]
    assert conflict["contract_id"] == "boolean_authoritative_conflict.v1"
    positive_ids = _authority_ids(conflict["positive_authorities"])
    negative_ids = _authority_ids(conflict["negative_authorities"])
    assert positive_ids
    assert negative_ids
    assert positive_ids.isdisjoint(negative_ids)
    return conflict


def _assert_conflict_terminal_result(result: Any) -> None:
    _assert_authoritative_conflict(result)
    assert result.answer == "unanswerable"
    assert result.guardrail_decision.action == "abstain"
    [slot] = result.evidence_bundle.metadata["query_plan"]["evidence_slots"]
    assert slot["status"] == "verified_conflict"


@pytest.mark.parametrize(
    ("route_policy", "allowed_routes", "agent_mode", "initial_route"),
    (
        ("doc", ["doc_text"], None, "doc_text"),
        ("auto", ["doc_text", "hybrid"], None, "doc_text"),
        ("auto", ["doc_text", "hybrid"], "thorough", "doc_text"),
    ),
    ids=("text_rag", "controller_auto", "crag_guarded"),
)
def test_complete_first_round_conflict_does_not_retry_or_switch_route(
    route_policy: str,
    allowed_routes: list[str],
    agent_mode: str | None,
    initial_route: str,
) -> None:
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        return {
            "evidence": [
                _evidence("positive-authority", POSITIVE_AUTHORITY),
                _evidence("negative-authority", NEGATIVE_AUTHORITY),
            ]
        }

    result = execute_controller_turn(
        _request(
            route_policy=route_policy,
            allowed_routes=allowed_routes,
            agent_mode=agent_mode,
        ),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert calls == [(initial_route, 1)]
    _assert_conflict_terminal_result(result)
    assert not _stage_events(
        result,
        "verifier_recovery",
        "route_switch",
        "critic",
        "focused_retrieval",
        "evidence_rebind",
        "reverify",
    )


@pytest.mark.parametrize(
    ("route_policy", "allowed_routes", "agent_mode"),
    (
        ("doc", ["doc_text"], None),
        ("auto", ["doc_text", "hybrid"], None),
        ("auto", ["doc_text", "hybrid"], "thorough"),
    ),
    ids=("text_rag", "controller_auto", "crag_guarded"),
)
def test_missing_authority_allows_at_most_one_recovery_and_abstains(
    route_policy: str,
    allowed_routes: list[str],
    agent_mode: str | None,
) -> None:
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        return {"evidence": [_evidence(f"missing-{len(calls)}", MISSING_AUTHORITY)]}

    result = execute_controller_turn(
        _request(
            route_policy=route_policy,
            allowed_routes=allowed_routes,
            agent_mode=agent_mode,
        ),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert len(calls) <= 2
    recovery_events = [
        event
        for event in result.controller_trace
        if event.get("verifier_recovery_attempt")
    ]
    assert recovery_events
    assert {event["verifier_recovery_attempt"] for event in recovery_events} == {1}
    [terminal] = _terminal_events(result)
    assert terminal["stop_reason"] == "authority_recovery_exhausted"
    assert result.answer == ABSTAIN_MESSAGE
    assert result.guardrail_decision.action == "abstain"
    assert result.verify_decision.status != "supported"


@pytest.mark.parametrize(
    (
        "route_policy",
        "allowed_routes",
        "agent_mode",
        "recovery_route",
        "uses_route_switch",
    ),
    (
        ("auto", ["doc_text", "hybrid"], None, "hybrid", True),
        ("auto", ["doc_text", "hybrid"], "thorough", "doc_text", False),
    ),
    ids=("controller_auto", "crag_guarded"),
)
def test_recovery_conflict_terminates_resolved_and_preserves_authority_sides(
    route_policy: str,
    allowed_routes: list[str],
    agent_mode: str | None,
    recovery_route: str,
    uses_route_switch: bool,
) -> None:
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        if request.retrieval_round_id == 1:
            evidence = [_evidence("missing-authority", MISSING_AUTHORITY)]
        else:
            evidence = [
                _evidence("positive-authority", POSITIVE_AUTHORITY),
                _evidence("negative-authority", NEGATIVE_AUTHORITY),
            ]
        return {"evidence": evidence}

    result = execute_controller_turn(
        _request(
            route_policy=route_policy,
            allowed_routes=allowed_routes,
            agent_mode=agent_mode,
        ),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert len(calls) == 2
    assert calls[0][1] == 1
    assert calls[1][1] == 2
    assert calls[1][0] == recovery_route
    _assert_conflict_terminal_result(result)
    [terminal] = _terminal_events(result)
    assert terminal["stop_reason"] == "authority_conflict_resolved"
    route_switches = _stage_events(result, "route_switch")
    assert bool(route_switches) is uses_route_switch


def test_crag_recovery_rebind_and_reverify_keep_both_conflicting_authorities() -> None:
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        if request.retrieval_round_id == 1:
            evidence = [_evidence("missing-authority", MISSING_AUTHORITY)]
        else:
            evidence = [
                _evidence("positive-authority", POSITIVE_AUTHORITY),
                _evidence("negative-authority", NEGATIVE_AUTHORITY),
            ]
        return {"evidence": evidence}

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
        event["stage"]
        for event in result.controller_trace
        if event.get("verifier_recovery_attempt") == 1
    ]
    assert recovery_stages == [
        "critic",
        "focused_retrieval",
        "evidence_rebind",
        "reverify",
    ]
    _assert_conflict_terminal_result(result)
    [terminal] = _terminal_events(result)
    assert terminal["stage"] == "reverify"
    assert terminal["stop_reason"] == "authority_conflict_resolved"
    assert not _stage_events(result, "route_switch")
