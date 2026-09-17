"""Old private patch paths and worker/signal sequencing, before extraction."""

from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa import route_budget as budget
from ktem_tests.route_stage_test_support import FakeSignal, ScheduledWorker


def timeout():
    return budget.RouteDeadlineExhausted("retrieval", 120, 3, 0)


@pytest.mark.parametrize("phase", ["start", "wait"])
@pytest.mark.parametrize("error", [None, ValueError("same error")])
def test_worker_result_or_exception_is_published_once(monkeypatch, phase, error):
    worker = ScheduledWorker(phase, error)
    monkeypatch.setattr(budget, "threading", worker.module())
    event: dict[str, Any] = {}
    args: dict[str, Any] = dict(
        on_timeout=timeout, on_cancel=worker.cancel, event=event
    )
    if error is None:
        assert budget._run_with_worker_timeout(3, worker.call, **args) == "value"
    else:
        with pytest.raises(ValueError) as caught:
            budget._run_with_worker_timeout(3, worker.call, **args)
        assert caught.value is error
    assert worker.calls == ["construct", "start", "backend", "completed"]
    assert worker.waits == [3]
    assert event == {}


@pytest.mark.parametrize(
    "phase,stopped", [("boundary", True), ("cancel", True), ("late", False)]
)
@pytest.mark.parametrize("error", [None, ValueError("late error")])
def test_timeout_clears_ready_or_late_results_before_cancellation(
    monkeypatch, phase, stopped, error
):
    worker = ScheduledWorker(phase, error)
    monkeypatch.setattr(budget, "threading", worker.module())
    event: dict[str, Any] = {}
    observed_at_wait = []
    worker.after_wait = lambda: observed_at_wait.append(dict(event))
    with pytest.raises(budget.RouteDeadlineExhausted) as caught:
        budget._run_with_worker_timeout(
            -1, worker.call, on_timeout=timeout, on_cancel=worker.cancel, event=event
        )
    assert caught.value == timeout()
    assert worker.waits == [0.000001, 0.1]
    assert observed_at_wait == [{"cancellation_error_types": ["LookupError"]}]
    expected = {
        "cancellation_error_types": ["LookupError"],
        "cancellation_status": "producer_stopped"
        if stopped
        else "producer_unresponsive",
    }
    assert event == expected
    if phase == "late":
        assert worker.target is not None
        worker.target()
    assert event == expected
    assert worker.calls.count("backend") == worker.calls.count("cancel") == 1
    assert worker.calls.count("construct") == worker.calls.count("start") == 1


def test_direct_worker_cancel_exception_propagates_without_observation(monkeypatch):
    worker = ScheduledWorker("late")
    monkeypatch.setattr(budget, "threading", worker.module())
    event: dict[str, Any] = {}
    error = LookupError("cancel operation itself failed")

    def cancel():
        raise error

    with pytest.raises(LookupError) as caught:
        budget._run_with_worker_timeout(
            3, worker.call, on_timeout=timeout, on_cancel=cancel, event=event
        )
    assert caught.value is error
    assert worker.waits == [3] and event == {}
    assert worker.target is not None
    worker.target()
    assert event == {}


def test_platform_and_worker_patch_paths_are_resolved_at_call_time(monkeypatch):
    calls: list[Any] = []

    def available():
        calls.append("available")
        return False

    monkeypatch.setattr(budget, "_signal_timeout_available", available)

    def worker(seconds, call, **kwargs):
        calls.append((seconds, kwargs))
        return call()

    monkeypatch.setattr(budget, "_run_with_worker_timeout", worker)
    event: dict[str, Any] = {}

    def cancel():
        return []

    assert (
        budget._run_with_interruptible_timeout(
            None, lambda: "unbounded", on_timeout=timeout, on_cancel=cancel, event=event
        )
        == "unbounded"
    )
    assert calls == []
    assert (
        budget._run_with_interruptible_timeout(
            3, lambda: "bounded", on_timeout=timeout, on_cancel=cancel, event=event
        )
        == "bounded"
    )
    assert calls == [
        "available",
        (3, {"on_timeout": timeout, "on_cancel": cancel, "event": event}),
    ]


@pytest.mark.parametrize("behavior", ["success", "exception", "timeout"])
@pytest.mark.parametrize("outer", [False, True])
def test_signal_restores_handler_and_outer_interval(monkeypatch, behavior, outer):
    signals = FakeSignal(40 if outer else 0, 3 if outer else 0)
    times = iter([100, 101])
    monkeypatch.setattr(budget, "signal", signals)
    monkeypatch.setattr(budget, "monotonic", lambda: next(times))
    monkeypatch.setattr(budget, "_signal_timeout_available", lambda: True)
    error = ValueError("backend failure")
    event: dict[str, Any] = {}

    def call():
        if behavior == "exception":
            raise error
        if behavior == "timeout":
            signals.handler(14, None)
        return "value"

    args: dict[str, Any] = dict(
        on_timeout=timeout, on_cancel=lambda: pytest.fail("cancelled"), event=event
    )
    if behavior == "success":
        assert budget._run_with_interruptible_timeout(3, call, **args) == "value"
    else:
        kind = ValueError if behavior == "exception" else budget.RouteDeadlineExhausted
        with pytest.raises(kind) as caught:
            budget._run_with_interruptible_timeout(3, call, **args)
        assert (
            caught.value is error
            if behavior == "exception"
            else caught.value == timeout()
        )
    assert signals.calls == [
        "get_handler",
        "get_timer",
        "install",
        ("timer", 3, 0),
        ("timer", 0, 0),
        "restore_handler",
        *([("timer", 39, 3)] if outer else []),
    ]
    assert signals.handler is signals.initial_handler and event == {}


def test_cancellation_callback_order_identity_and_errors(monkeypatch):
    calls = []
    cancel_event: Any = SimpleNamespace(set=lambda: calls.append("event"))

    class Backend:
        def run(self):
            pytest.fail("backend invoked")

        def cancel(self):
            calls.append("backend")
            raise RuntimeError("backend cancel")

    def callback(stage):
        calls.append(stage)
        raise LookupError("callback cancel")

    backend = Backend()
    request = SimpleNamespace(route_cancel_callback=callback)
    assert budget._cancel_blocking_route_stage(
        request, "retrieval", backend.run, cancel_event
    ) == ["LookupError", "RuntimeError"]
    assert calls == ["event", "retrieval", "backend"]
    request.route_cancel_callback = backend.cancel
    calls.clear()
    assert budget._cancel_blocking_route_stage(
        request, "retrieval", backend.run, cancel_event
    ) == ["TypeError"]
    assert calls == ["event"]
