from __future__ import annotations

import threading
import time
from time import monotonic

import ktem.docqa.execution as execution_module
import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn
from ktem.docqa.route_budget import RouteDeadlineExhausted, run_blocking_route_stage
from ktem.docqa.terminal_semantic_commit import (
    build_terminal_semantic_commit,
    terminal_commit_projection_present,
)


def _request(*, timeout: float | None = None) -> DocQARequest:
    request = DocQARequest(
        prompt="Which input does the method use?",
        retrieval_query="method input",
        task_type="free_text",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        origin="benchmark",
        route_timeout_seconds=timeout,
        route_deadline_monotonic=(
            monotonic() + timeout if timeout is not None else None
        ),
    )
    request.route_terminal_reserve_seconds = 0.01
    return request


def test_answered_and_safe_abstention_have_mutually_exclusive_outcomes() -> None:
    evidence = {
        "evidence_id": "input",
        "source_id": "paper",
        "text": "The method uses labeled features.",
    }
    answered_request = _request()
    answered_request.verification_domain = "general"
    answered = execute_controller_turn(
        answered_request,
        retrieve=lambda *_args: {"evidence": [evidence]},
        generate=lambda *_args: "The method uses labeled features.",
    )
    abstained = execute_controller_turn(
        _request(),
        retrieve=lambda *_args: {"evidence": []},
        generate=lambda *_args: "must not run",
    )

    assert answered.engine_terminal_commit["outcome"] == "answered"
    assert answered.engine_terminal_commit["semantic_answer"] == (
        "The method uses labeled features."
    )
    assert answered.engine_terminal_commit["presentation_answer"] == (
        "The method uses labeled features."
    )
    assert abstained.engine_terminal_commit["outcome"] == "safe_abstention"
    assert abstained.engine_terminal_commit["semantic_answer"] == "unanswerable"
    assert abstained.engine_terminal_commit["presentation_answer"] == ABSTAIN_MESSAGE
    assert terminal_commit_projection_present(answered.engine_terminal_commit)
    assert terminal_commit_projection_present(abstained.engine_terminal_commit)


def test_route_deadline_is_timeout_not_safe_abstention() -> None:
    request = _request(timeout=0.08)

    def slow_retrieval(*_args):
        time.sleep(0.2)
        return {"evidence": []}

    result = execute_controller_turn(
        request,
        retrieve=slow_retrieval,
        generate=lambda *_args: "must not run",
    )

    commit = result.engine_terminal_commit
    assert commit["outcome"] == "timeout"
    assert commit["outcome_reason"] == "route_deadline_exhausted"
    assert commit["semantic_answer"] == "unanswerable"
    assert commit["presentation_answer"] == ABSTAIN_MESSAGE
    assert terminal_commit_projection_present(commit)


@pytest.mark.parametrize("failure_stage", ("planning", "retrieval", "generation"))
def test_operational_exception_commits_execution_failed(
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
) -> None:
    request = _request()

    if failure_stage == "planning":
        monkeypatch.setattr(
            execution_module,
            "_planned_execution",
            lambda *_args: (_ for _ in ()).throw(RuntimeError("planner failed")),
        )

    def retrieve(*_args):
        if failure_stage == "retrieval":
            raise RuntimeError("backend failed")
        return {
            "evidence": [
                {
                    "evidence_id": "input",
                    "source_id": "paper",
                    "text": "The method uses labeled features.",
                }
            ]
        }

    def generate(*_args):
        if failure_stage == "generation":
            raise RuntimeError("backend failed")
        return "The method uses labeled features."

    result = execute_controller_turn(request, retrieve=retrieve, generate=generate)

    commit = result.engine_terminal_commit
    assert commit["outcome"] == "execution_failed"
    assert commit["outcome_reason"] == f"{failure_stage}_failed"
    assert commit["semantic_answer"] == "unanswerable"
    assert commit["presentation_answer"] == ABSTAIN_MESSAGE
    assert commit["citations"] == []
    assert result.guardrail_decision.action == "error"
    assert terminal_commit_projection_present(commit)


def test_cancelled_commit_cannot_be_classified_as_safe_abstention() -> None:
    commit = build_terminal_semantic_commit(
        ABSTAIN_MESSAGE,
        {"status": "cancelled", "action": "cancel"},
        {"status": "cancelled", "action": "cancel"},
        {"items": [], "metadata": {}},
        outcome="cancelled",
        outcome_reason="user_cancelled",
        presentation_answer="Answer generation was cancelled.",
    ).as_dict()

    assert commit["outcome"] == "cancelled"
    assert commit["outcome_reason"] == "user_cancelled"
    assert commit["semantic_answer"] == "unanswerable"
    assert commit["presentation_answer"] == "Answer generation was cancelled."
    assert terminal_commit_projection_present(commit)


def test_non_main_thread_timeout_actively_cancels_and_joins_producer() -> None:
    request = _request(timeout=0.08)
    request.route_terminal_reserve_seconds = 0.0
    producer_stopped = threading.Event()
    cancellation_called = threading.Event()

    def cancel(_stage: str) -> None:
        cancellation_called.set()

    setattr(request, "route_cancel_callback", cancel)

    def blocking_backend() -> str:
        cancel_event = getattr(request, "route_call_cancel_event")
        fallback_deadline = monotonic() + 0.5
        try:
            while not cancel_event.wait(0.005) and monotonic() < fallback_deadline:
                pass
            return "cancelled"
        finally:
            producer_stopped.set()

    observed: list[RouteDeadlineExhausted] = []

    def invoke() -> None:
        try:
            run_blocking_route_stage(request, "backend", blocking_backend)
        except RouteDeadlineExhausted as exc:
            observed.append(exc)

    caller = threading.Thread(target=invoke, daemon=True)
    caller.start()
    caller.join(timeout=0.3)

    assert not caller.is_alive()
    assert len(observed) == 1
    assert isinstance(observed[0], RouteDeadlineExhausted)
    assert cancellation_called.is_set()
    assert producer_stopped.wait(0.05)
    [event] = getattr(request, "route_budget_trace")
    assert event["status"] == "deadline_exhausted"
    assert event["cancellation_status"] == "producer_stopped"
