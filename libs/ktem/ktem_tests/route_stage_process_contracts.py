"""Real platform mechanisms exercised only in an exclusively owned subprocess."""

import json
import logging
import signal
import sys
import threading
import time
from typing import Any

from ktem.docqa import route_budget as budget


def deadline():
    return budget.RouteDeadlineExhausted("native", 120, 0.04, 0)


def native_worker(behavior):
    release = threading.Event()
    cancellation = threading.Event()
    stopped = threading.Event()
    workers = []
    calls = []
    event: dict[str, Any] = {}
    observed: list[Any] = []

    def backend():
        workers.append(threading.current_thread())
        calls.append("backend")
        try:
            if behavior == "fast":
                return "value"
            if behavior == "error":
                raise ValueError("original error")
            assert cancellation.wait(2), "caller never requested cancellation"
            if behavior.startswith("late"):
                assert release.wait(2), "test never released its own producer"
            if behavior == "late-error":
                raise ValueError("late error")
            return "late value"
        finally:
            stopped.set()

    def cancel():
        calls.append("cancel")
        cancellation.set()
        return ["LookupError"] if behavior == "cancel-error-types" else []

    def invoke():
        assert not budget._signal_timeout_available()
        try:
            observed.append(
                budget._run_with_interruptible_timeout(
                    0.04, backend, on_timeout=deadline, on_cancel=cancel, event=event
                )
            )
        except Exception as error:
            logging.getLogger(__name__).debug(
                "Owned caller observed failure", exc_info=True
            )
            observed.append(error)

    caller = threading.Thread(target=invoke, name="r4c-owned-caller")
    caller.start()
    try:
        caller.join(2)
        assert not caller.is_alive() and len(observed) == 1
        _assert_worker_result(behavior, observed, event, calls, cancellation, stopped)
    finally:
        release.set()
        cancellation.set()
        caller.join(2)
        for worker in workers:
            worker.join(2)
        assert not caller.is_alive() and all(
            not worker.is_alive() for worker in workers
        )
    assert stopped.is_set() and len(observed) == 1
    return {
        "behavior": behavior,
        "calls": calls,
        "event": event,
        "result_type": type(observed[0]).__name__,
        "owned_workers_joined": len(workers),
    }


def _assert_worker_result(behavior, observed, event, calls, cancellation, stopped):
    if behavior == "fast":
        assert observed == ["value"] and event == {} and calls == ["backend"]
    elif behavior == "error":
        assert type(observed[0]) is ValueError and str(observed[0]) == "original error"
        assert event == {} and calls == ["backend"]
    else:
        assert type(observed[0]) is budget.RouteDeadlineExhausted
        expected = (
            "producer_unresponsive"
            if behavior.startswith("late")
            else "producer_stopped"
        )
        assert event["cancellation_status"] == expected and cancellation.is_set()
        assert stopped.is_set() == (expected == "producer_stopped")
        assert calls == ["backend", "cancel"]


def native_signal(behavior):
    assert budget._signal_timeout_available()
    signals: Any = signal
    original_handler = signals.getsignal(signals.SIGALRM)
    outer_seen = []

    def outer_handler(_signum, _frame):
        outer_seen.append("alarm")
        raise AssertionError("later outer alarm fired early")

    signals.signal(signals.SIGALRM, outer_handler)
    outer = behavior in {"outer", "exception", "nested"}
    if outer:
        signals.setitimer(signals.ITIMER_REAL, 2, 0.75)
    started = time.monotonic()
    result = None

    def call():
        if behavior == "exception":
            raise ValueError("original signal error")
        if behavior == "nested":
            return budget._run_with_interruptible_timeout(
                0.02,
                lambda: time.sleep(1),
                on_timeout=deadline,
                on_cancel=lambda: [],
                event={},
            )
        if behavior == "timeout":
            time.sleep(1)
        return "value"

    def cancelled():
        outer_seen.append("cancel")
        return []

    try:
        try:
            result = budget._run_with_interruptible_timeout(
                0.08,
                call,
                on_timeout=deadline,
                on_cancel=cancelled,
                event={},
            )
        except (ValueError, budget.RouteDeadlineExhausted) as error:
            result = type(error).__name__
        assert (
            result
            == {
                "success": "value",
                "outer": "value",
                "exception": "ValueError",
                "nested": "RouteDeadlineExhausted",
                "timeout": "RouteDeadlineExhausted",
            }[behavior]
        )
        delay, interval = signals.getitimer(signals.ITIMER_REAL)
        assert signals.getsignal(signals.SIGALRM) is outer_handler
        if outer:
            assert 0 < delay <= 2 and interval == 0.75
            assert abs((2 - delay) - (time.monotonic() - started)) < 0.1
        else:
            assert (delay, interval) == (0, 0)
        assert outer_seen == []
        return {
            "behavior": behavior,
            "result": result,
            "handler_restored": True,
            "interval": interval,
            "outer_delay": delay,
        }
    finally:
        signals.setitimer(signals.ITIMER_REAL, 0)
        signals.signal(signals.SIGALRM, original_handler)


def main():
    mechanism = sys.argv[1]
    if mechanism == "worker":
        cases = [
            "fast",
            "error",
            "cooperative",
            "late-value",
            "late-error",
            "cancel-error-types",
        ]
        records = [native_worker(case) for case in cases]
    else:
        assert mechanism == "signal"
        records = [
            native_signal(case)
            for case in ("success", "outer", "exception", "nested", "timeout")
        ]
    print(
        json.dumps(
            {"platform": sys.platform, "mechanism": mechanism, "records": records}
        )
    )


if __name__ == "__main__":
    main()
