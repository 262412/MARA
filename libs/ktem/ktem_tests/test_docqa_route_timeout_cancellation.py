from __future__ import annotations

import threading
import time
from time import monotonic
from types import SimpleNamespace
from typing import Any, Callable

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.route_budget import (
    DEFAULT_TERMINAL_COMMIT_RESERVE_SECONDS,
    RouteDeadlineExhausted,
    route_call_timeout_seconds,
    run_blocking_route_stage,
)


def _request(timeout_seconds: float) -> SimpleNamespace:
    return SimpleNamespace(
        route_timeout_seconds=timeout_seconds,
        route_deadline_monotonic=monotonic() + timeout_seconds,
        route_terminal_reserve_seconds=0.0,
    )


def _run_in_caller_thread(
    call: Callable[[], Any],
) -> tuple[threading.Thread, list[Any]]:
    observed: list[Any] = []

    def invoke() -> None:
        try:
            observed.append(call())
        except RouteDeadlineExhausted as error:
            observed.append(error)

    caller = threading.Thread(target=invoke, name="route-caller", daemon=True)
    caller.start()
    return caller, observed


def test_non_main_thread_fast_result_is_returned_without_cancellation() -> None:
    request = _request(0.5)
    cancelled: list[str] = []
    request.route_cancel_callback = cancelled.append

    caller, observed = _run_in_caller_thread(
        lambda: run_blocking_route_stage(request, "retrieval", lambda: "evidence")
    )
    caller.join(timeout=0.3)

    assert not caller.is_alive()
    assert observed == ["evidence"]
    assert cancelled == []
    [event] = request.route_budget_trace
    assert event["status"] == "completed"
    assert "cancellation_status" not in event


def test_non_main_thread_timeout_cancels_once_and_joins_cooperative_producer() -> None:
    request = _request(0.06)
    cancelled: list[str] = []
    producer_stopped = threading.Event()
    request.route_cancel_callback = cancelled.append

    def blocking_backend() -> str:
        cancel_event = request.route_call_cancel_event
        try:
            cancel_event.wait(timeout=0.5)
            return "late evidence"
        finally:
            producer_stopped.set()

    caller, observed = _run_in_caller_thread(
        lambda: run_blocking_route_stage(request, "retrieval", blocking_backend)
    )
    caller.join(timeout=0.3)

    assert not caller.is_alive()
    assert len(observed) == 1
    assert isinstance(observed[0], RouteDeadlineExhausted)
    assert cancelled == ["retrieval"]
    assert producer_stopped.is_set()
    [event] = request.route_budget_trace
    assert event["status"] == "deadline_exhausted"
    assert event["cancellation_status"] == "producer_stopped"


def test_late_worker_result_cannot_replace_timeout_terminal_state() -> None:
    request = _request(0.03)
    release_late_result = threading.Event()
    producer_stopped = threading.Event()
    terminal_state: dict[str, str] = {}

    def unresponsive_backend() -> str:
        request.route_call_cancel_event.wait(timeout=0.5)
        release_late_result.wait(timeout=0.5)
        producer_stopped.set()
        return "late evidence"

    def invoke() -> None:
        try:
            terminal_state["outcome"] = run_blocking_route_stage(
                request,
                "retrieval",
                unresponsive_backend,
            )
        except RouteDeadlineExhausted:
            terminal_state["outcome"] = "timeout"

    caller = threading.Thread(target=invoke, name="route-caller", daemon=True)
    caller.start()
    caller.join(timeout=0.25)

    assert not caller.is_alive()
    assert terminal_state == {"outcome": "timeout"}
    [event] = request.route_budget_trace
    assert event["status"] == "deadline_exhausted"
    assert event["cancellation_status"] == "producer_unresponsive"

    release_late_result.set()
    assert producer_stopped.wait(timeout=0.2)
    time.sleep(0.01)
    assert terminal_state == {"outcome": "timeout"}


def test_non_main_timeout_publishes_no_late_evidence_or_authority() -> None:
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
        route_timeout_seconds=0.05,
        route_deadline_monotonic=monotonic() + 0.05,
        route_terminal_reserve_seconds=0.0,
    )
    producer_stopped = threading.Event()

    def late_retrieval(*_args: Any) -> dict[str, Any]:
        cancel_event = getattr(request, "route_call_cancel_event")
        cancel_event.wait(timeout=0.5)
        producer_stopped.set()
        return {
            "evidence": [
                {
                    "evidence_id": "late",
                    "source_id": "paper",
                    "text": "This evidence arrived after cancellation.",
                }
            ]
        }

    caller, observed = _run_in_caller_thread(
        lambda: execute_controller_turn(
            request,
            retrieve=late_retrieval,
            generate=lambda *_args: "must not run",
        )
    )
    caller.join(timeout=0.3)

    assert not caller.is_alive()
    assert producer_stopped.is_set()
    [result] = observed
    assert result.engine_terminal_commit["outcome"] == "timeout"
    assert result.engine_terminal_commit["authoritative_evidence"] == []
    assert result.engine_terminal_commit["citations"] == []
    assert result.evidence_bundle.items == []


def test_bound_backend_cancel_is_invoked_on_timeout() -> None:
    request = _request(0.04)

    class Backend:
        def __init__(self) -> None:
            self.cancelled = threading.Event()
            self.stopped = threading.Event()

        def run(self) -> str:
            try:
                self.cancelled.wait(timeout=0.5)
                return "late evidence"
            finally:
                self.stopped.set()

        def cancel(self) -> None:
            self.cancelled.set()

    backend = Backend()
    caller, observed = _run_in_caller_thread(
        lambda: run_blocking_route_stage(request, "retrieval", backend.run)
    )
    caller.join(timeout=0.3)

    assert not caller.is_alive()
    assert len(observed) == 1
    assert isinstance(observed[0], RouteDeadlineExhausted)
    assert backend.cancelled.is_set()
    assert backend.stopped.is_set()


def test_a3_does_not_increase_timeout_or_terminal_reserve() -> None:
    request = SimpleNamespace()

    assert (
        route_call_timeout_seconds(
            request,
            configured_timeout_seconds=240.0,
        )
        == 240.0
    )
    assert DEFAULT_TERMINAL_COMMIT_RESERVE_SECONDS == 12.0
