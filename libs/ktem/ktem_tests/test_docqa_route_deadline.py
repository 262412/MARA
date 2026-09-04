from __future__ import annotations

import time
from time import monotonic

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn
from ktem.docqa.route_budget import optional_stage_allowed, route_budget_metadata
from ktem.docqa.terminal_semantic_commit import terminal_commit_projection_present


def _request(timeout_seconds: float) -> DocQARequest:
    request = DocQARequest(
        prompt="What does the paper report?",
        retrieval_query="paper report",
        task_type="free_text",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        origin="benchmark",
        route_timeout_seconds=timeout_seconds,
        route_deadline_monotonic=monotonic() + timeout_seconds,
    )
    request.route_terminal_reserve_seconds = 0.02
    return request


def test_blocking_retrieval_commits_typed_deadline_abstention_before_outer_timeout() -> (
    None
):
    started = monotonic()

    def slow_retrieve(*_args):
        time.sleep(0.3)
        return {
            "evidence": [
                {
                    "evidence_id": "late",
                    "source_id": "paper",
                    "text": "This result arrived after the route deadline.",
                }
            ]
        }

    result = execute_controller_turn(
        _request(0.1),
        retrieve=slow_retrieve,
        generate=lambda *_args: "late answer",
    )

    assert monotonic() - started < 0.2
    assert result.answer == ABSTAIN_MESSAGE
    assert result.engine_terminal_answer == "unanswerable"
    assert result.engine_terminal_commit["semantic_answer"] == "unanswerable"
    assert result.engine_terminal_commit["answer_status"] == "abstained"
    assert terminal_commit_projection_present(result.engine_terminal_commit)
    assert result.verify_decision.status == "not_enough_evidence"
    assert result.verify_decision.reason == "route_deadline_exhausted"
    assert result.guardrail_decision.action == "abstain"
    assert result.verify_decision.verified_citations == []
    assert result.engine_terminal_commit["citations"] == []
    assert result.evidence_bundle.items == []
    deadline_events = [
        event
        for event in result.controller_trace
        if event.get("stage") == "route_deadline"
    ]
    assert deadline_events
    assert deadline_events[-1]["blocking_stage"] == "retrieval"
    assert deadline_events[-1]["stop_reason"] == "route_deadline_exhausted"
    assert deadline_events[-1]["absolute_deadline_monotonic"] > 0
    assert deadline_events[-1]["call_timeout_budget_seconds"] > 0


def test_expired_deadline_does_not_start_retrieval_or_generation() -> None:
    request = _request(0.1)
    request.route_deadline_monotonic = monotonic() - 1.0
    calls: list[str] = []

    def retrieve(*_args):
        calls.append("retrieve")
        return {"evidence": []}

    def generate(*_args):
        calls.append("generate")
        return "answer"

    result = execute_controller_turn(
        request,
        retrieve=retrieve,
        generate=generate,
    )

    assert calls == []
    assert result.engine_terminal_answer == "unanswerable"
    assert result.verify_decision.reason == "route_deadline_exhausted"
    assert terminal_commit_projection_present(result.engine_terminal_commit)


def test_generation_deadline_preserves_last_completed_evidence_bundle() -> None:
    request = _request(0.1)
    evidence = {
        "evidence_id": "completed-retrieval",
        "source_id": "paper",
        "section_id": "results",
        "text": "The paper reports a completed retrieval result.",
    }

    def slow_generate(*_args):
        time.sleep(0.3)
        return "late answer"

    result = execute_controller_turn(
        request,
        retrieve=lambda *_args: {"evidence": [evidence]},
        generate=slow_generate,
    )

    assert result.engine_terminal_answer == "unanswerable"
    assert result.verify_decision.reason == "route_deadline_exhausted"
    assert [item["evidence_id"] for item in result.evidence_bundle.items] == [
        "completed-retrieval"
    ]
    [deadline] = [
        event
        for event in result.controller_trace
        if event.get("stage") == "route_deadline"
    ]
    assert deadline["blocking_stage"] == "generation"


def test_optional_stage_reserve_uses_observed_blocking_call_cost() -> None:
    request = _request(13.0)
    request.route_terminal_reserve_seconds = 0.0
    setattr(
        request,
        "route_budget_trace",
        [
            {
                "blocking_stage": "retrieval",
                "status": "completed",
                "elapsed_seconds": 20.0,
            }
        ],
    )

    assert optional_stage_allowed(request) is False
    assert route_budget_metadata(request)["optional_stage_reserve_seconds"] == 20.0
