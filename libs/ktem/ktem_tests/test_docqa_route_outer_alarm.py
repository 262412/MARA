"""An earlier outer deadline must keep its exception and must not fire twice."""

import json
import os
import subprocess
import sys

import pytest
from ktem.docqa import route_budget as budget
from ktem_tests.route_stage_test_support import FakeSignal


@pytest.mark.parametrize("interval", [0, 4])
def test_earlier_outer_alarm_keeps_deadline_identity_and_consumption(
    monkeypatch, interval
):
    signals = FakeSignal(2, interval)
    error = TimeoutError("outer request expired")
    clock = [100.0]
    seen = []

    def outer(signum, frame):
        seen.append((signum, frame))
        raise error

    signals.initial_handler = signals.handler = outer
    monkeypatch.setattr(budget, "signal", signals)
    monkeypatch.setattr(budget, "monotonic", lambda: clock[0])
    monkeypatch.setattr(budget, "_signal_timeout_available", lambda: True)
    frame = object()

    def call():
        assert signals.timer == (2, 0), "inner timer postponed the outer deadline"
        clock[0] = 102
        signals.handler(14, frame)

    with pytest.raises(TimeoutError) as caught:
        budget._run_with_interruptible_timeout(
            10,
            call,
            on_timeout=lambda: budget.RouteDeadlineExhausted("inner", 200, 10, 0),
            on_cancel=lambda: [],
            event={},
        )
    assert caught.value is error and seen == [(14, frame)]
    assert signals.handler is outer
    assert signals.timer == ((4, 4) if interval else (0, 0))


@pytest.mark.parametrize("interval", [0, 2])
def test_returning_outer_handler_does_not_remove_inner_bound(monkeypatch, interval):
    signals = FakeSignal(2, interval)
    clock = [100.0]
    seen = []

    def outer(_signum, _frame):
        seen.append(clock[0])

    signals.initial_handler = signals.handler = outer
    monkeypatch.setattr(budget, "signal", signals)
    monkeypatch.setattr(budget, "monotonic", lambda: clock[0])
    monkeypatch.setattr(budget, "_signal_timeout_available", lambda: True)
    error = budget.RouteDeadlineExhausted("inner", 200, 5, 0)

    def call():
        assert signals.timer == (2, 0)
        clock[0] = 102
        signals.handler(14, None)
        assert signals.timer == ((2, 0) if interval else (3, 0))
        if interval:
            clock[0] = 104
            signals.handler(14, None)
            assert signals.timer == (1, 0)
        clock[0] = 105
        signals.handler(14, None)

    with pytest.raises(budget.RouteDeadlineExhausted) as caught:
        budget._run_with_interruptible_timeout(
            5,
            call,
            on_timeout=lambda: error,
            on_cancel=lambda: [],
            event={},
        )
    assert caught.value is error
    assert seen == ([102, 104] if interval else [102])
    assert signals.handler is outer
    assert signals.timer == ((1, 2) if interval else (0, 0))


def test_outer_alarm_native_platform_receipt():
    receipt = {"platform": sys.platform, "native_signal_executed": False}
    if sys.platform.startswith("linux"):
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "ktem_tests.route_outer_alarm_process"],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        observed = json.loads(completed.stdout)
        assert len(observed["records"]) == 5 and observed["owned_timers_cleared"]
        receipt.update(native_signal_executed=True, observation=observed)
    print("R4C_OUTER_ALARM " + json.dumps(receipt))
