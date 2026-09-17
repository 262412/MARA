"""Fixed budget and request-state expectations established before R4-C extraction."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa import route_budget as budget


@pytest.mark.parametrize("deadline", [None, "", 0, 100, 115, "115"])
def test_remaining_deadline_and_original_clock_reads(monkeypatch, deadline):
    calls = []

    def clock():
        calls.append("clock")
        return 100

    monkeypatch.setattr(budget, "monotonic", clock)
    request = SimpleNamespace(route_deadline_monotonic=deadline)
    expected = None if deadline in (None, "") else max(0, float(deadline) - 100)
    assert budget.remaining_route_seconds(request) == expected
    assert calls == ([] if deadline in (None, "") else ["clock"])


@pytest.mark.parametrize(
    "deadline,configured,reserve,expected",
    [
        (None, None, None, None),
        ("", 8, None, 8),
        (None, 0, None, 0),
        (None, -5, None, 0),
        (100, None, None, 0),
        (110, 90, None, 0),
        (120, None, None, 8),
        (120, 5, None, 5),
        (120, 50, None, 8),
        (120, -3, None, 0),
        (120, 0, None, 0),
        (120, None, "", 8),
        (120, None, -2, 20),
        (120, None, "3.5", 16.5),
    ],
)
def test_call_timeout_formula(monkeypatch, deadline, configured, reserve, expected):
    monkeypatch.setattr(budget, "monotonic", lambda: 100)
    request = SimpleNamespace(
        route_deadline_monotonic=deadline, route_terminal_reserve_seconds=reserve
    )
    assert (
        budget.route_call_timeout_seconds(
            request, configured_timeout_seconds=configured
        )
        == expected
    )


@pytest.mark.parametrize("remaining,allowed", [(0, False), (24, False), (24.001, True)])
def test_optional_comparison_is_strict_and_keeps_both_reserves(
    monkeypatch, remaining, allowed
):
    monkeypatch.setattr(budget, "monotonic", lambda: 100)
    request = SimpleNamespace(route_deadline_monotonic=100 + remaining)
    assert budget.optional_stage_allowed(request) is allowed
    assert request.route_budget_trace == []
    assert budget.DEFAULT_OPTIONAL_STAGE_RESERVE_SECONDS == 12
    assert budget.DEFAULT_TERMINAL_COMMIT_RESERVE_SECONDS == 12


def test_optional_reserve_reads_completed_costs_each_time(monkeypatch):
    monkeypatch.setattr(budget, "monotonic", lambda: 100)
    trace: list[dict[str, Any]] = [
        {"status": "failed", "elapsed_seconds": 500},
        {"status": "completed", "elapsed_seconds": 20},
        {"status": "completed", "elapsed_seconds": None},
    ]
    request = SimpleNamespace(route_deadline_monotonic=132, route_budget_trace=trace)
    assert not budget.optional_stage_allowed(request)
    trace[1]["elapsed_seconds"] = 19
    assert budget.optional_stage_allowed(request)
    assert budget.optional_stage_reserve_seconds(request, minimum_seconds=-1) == 19
    assert budget.route_budget_metadata(request) == {
        "route_timeout_seconds": None,
        "remaining_route_seconds": 32,
        "absolute_deadline_monotonic": 132,
        "terminal_commit_reserve_seconds": 12,
        "optional_stage_reserve_seconds": 19,
    }


def test_no_deadline_fast_path_has_no_clock_state_install_or_trace(monkeypatch):
    monkeypatch.setattr(budget, "monotonic", lambda: pytest.fail("clock read"))
    marker = object()
    request = SimpleNamespace(route_call_timeout_seconds=marker)
    calls = []

    def call(a, *, b):
        calls.append((a, b))
        return marker

    assert budget.run_blocking_route_stage(request, "fast", call, 1, b=2) is marker
    assert calls == [(1, 2)]
    assert vars(request) == {
        "route_call_timeout_seconds": marker,
        "route_last_blocking_stage": "fast",
    }


@pytest.mark.parametrize("error", [ValueError("ordinary"), KeyboardInterrupt("stop")])
def test_fast_path_original_exception_and_failed_stage(monkeypatch, error):
    request = SimpleNamespace()
    monkeypatch.setattr(budget, "monotonic", lambda: pytest.fail("clock read"))

    def fail():
        raise error

    with pytest.raises(type(error)) as caught:
        budget.run_blocking_route_stage(request, "generation", fail)
    assert caught.value is error
    assert getattr(request, "route_failed_stage", None) == (
        "generation" if isinstance(error, Exception) else None
    )
    assert not hasattr(request, "route_budget_trace")


def test_clock_read_order_trace_and_original_absent_state_restoration(monkeypatch):
    readings = iter([100, 101, 102, 103, 104, 105])
    observed: list[Any] = []

    def clock():
        value = next(readings)
        observed.append(value)
        return value

    def execute(timeout, call, **_kwargs):
        observed.append(("execute", timeout))
        return call()

    monkeypatch.setattr(budget, "monotonic", clock)
    monkeypatch.setattr(budget, "_run_with_interruptible_timeout", execute)
    request = SimpleNamespace(route_deadline_monotonic=150)
    marker = object()
    assert (
        budget.run_blocking_route_stage(request, "retrieval", lambda: marker) is marker
    )
    assert observed == [100, 101, 102, ("execute", 37), 103, 104, 105]
    assert request.route_budget_trace == [
        {
            "stage": "route_budget",
            "blocking_stage": "retrieval",
            "absolute_deadline_monotonic": 150,
            "remaining_route_seconds_before": 50,
            "terminal_commit_reserve_seconds": 12,
            "configured_call_timeout_seconds": None,
            "call_timeout_budget_seconds": 37,
            "status": "completed",
            "elapsed_seconds": 2,
            "remaining_route_seconds_after": 45,
        }
    ]
    assert request.route_deadline_monotonic == 150
    assert not hasattr(request, "route_call_timeout_seconds")
    assert not hasattr(request, "route_call_cancel_event")


@pytest.mark.parametrize("configured", [None, 0, -1])
def test_exhausted_budget_short_circuits_before_installation(monkeypatch, configured):
    monkeypatch.setattr(budget, "monotonic", lambda: 100)
    marker = object()
    request = SimpleNamespace(
        route_deadline_monotonic=110,
        route_call_cancel_event=marker,
        route_call_timeout_seconds=99,
    )
    with pytest.raises(budget.RouteDeadlineExhausted) as caught:
        budget.run_blocking_route_stage(
            request,
            "retrieval",
            lambda: pytest.fail("backend called"),
            configured_timeout_seconds=configured,
        )
    assert caught.value == budget.RouteDeadlineExhausted("retrieval", 110, 0, 10)
    assert request.route_budget_trace[0]["status"] == "deadline_exhausted_before_call"
    assert "elapsed_seconds" not in request.route_budget_trace[0]
    assert request.route_call_cancel_event is marker
    assert request.route_call_timeout_seconds == 99
    assert not hasattr(request, "route_failed_stage")


@pytest.mark.parametrize("initial", ["absent", "none", "value"])
def test_nested_call_state_and_deadline_are_restored(monkeypatch, initial):
    monkeypatch.setattr(budget, "monotonic", lambda: 100)
    monkeypatch.setattr(
        budget, "_run_with_interruptible_timeout", lambda _timeout, call, **_kw: call()
    )
    original = object()
    request = SimpleNamespace(route_deadline_monotonic=200)
    if initial != "absent":
        request.route_call_cancel_event = original if initial == "value" else None
        request.route_call_timeout_seconds = 71 if initial == "value" else None
    events = []

    def inner():
        events.append(request.route_call_cancel_event)
        assert request.route_call_timeout_seconds == 4
        assert request.route_deadline_monotonic == 200
        raise ValueError("inner failed")

    def outer():
        parent_event = request.route_call_cancel_event
        events.append(parent_event)
        with pytest.raises(ValueError, match="inner failed"):
            budget.run_blocking_route_stage(
                request, "inner", inner, configured_timeout_seconds=4
            )
        assert request.route_call_cancel_event is parent_event
        assert request.route_call_timeout_seconds == 8
        return "outer"

    assert (
        budget.run_blocking_route_stage(
            request, "outer", outer, configured_timeout_seconds=8
        )
        == "outer"
    )
    assert events[0] is not events[1]
    assert request.route_last_blocking_stage == request.route_failed_stage == "inner"
    assert [e["status"] for e in request.route_budget_trace] == ["completed", "failed"]
    assert request.route_budget_trace[1]["error_type"] == "ValueError"
    assert request.route_deadline_monotonic == 200
    if initial == "value":
        assert request.route_call_cancel_event is original
        assert request.route_call_timeout_seconds == 71
    else:
        assert not hasattr(request, "route_call_timeout_seconds")
        assert not hasattr(request, "route_call_cancel_event")


def test_trace_copy_and_timeout_exception_identity(monkeypatch):
    monkeypatch.setattr(budget, "monotonic", lambda: 100)
    nested: dict[str, list[int]] = {"x": []}
    request = SimpleNamespace(route_budget_trace=[{"nested": nested}])
    projected = budget.route_budget_trace(request)
    assert projected is not request.route_budget_trace
    assert projected[0] is not request.route_budget_trace[0]
    assert projected[0]["nested"] is nested
    error = budget.RouteDeadlineExhausted("generation", 123, 1.23456789, 0)
    assert type(error).__module__ == "ktem.docqa.route_budget"
    assert isinstance(error, TimeoutError)
    assert (
        str(error) == "Route deadline exhausted during generation after 1.2346 seconds."
    )
    with pytest.raises(FrozenInstanceError):
        setattr(error, "blocking_stage", "changed")
    assert budget.deadline_trace_event(request, error) == {
        "stage": "route_deadline",
        "blocking_stage": "generation",
        "absolute_deadline_monotonic": 123,
        "call_timeout_budget_seconds": 1.234568,
        "remaining_route_seconds": 0,
        "stop_reason": "route_deadline_exhausted",
    }
