"""POSIX outer-alarm regressions; every timer belongs to this child process."""

import json
import signal
import sys
import time
from typing import Any

from ktem.docqa import route_budget as budget

from benchmark.route_timeout import RouteExecutionTimeout, run_with_route_timeout


def bounded(seconds, call, error):
    return budget._run_with_interruptible_timeout(
        seconds, call, on_timeout=lambda: error, on_cancel=lambda: [], event={}
    )


def outer_case(interval):
    signals: Any = signal
    error = TimeoutError("outer expires first")
    seen = []

    def handler(_signum, _frame):
        seen.append("outer")
        raise error

    signals.signal(signals.SIGALRM, handler)
    signals.setitimer(signals.ITIMER_REAL, 0.03, interval)
    try:
        bounded(
            0.3,
            lambda: time.sleep(1),
            budget.RouteDeadlineExhausted("inner", 2, 0.3, 0),
        )
    except TimeoutError as caught:
        assert caught is error
    else:
        raise AssertionError("outer timeout was lost")
    delay, actual_interval = signals.getitimer(signals.ITIMER_REAL)
    assert signals.getsignal(signals.SIGALRM) is handler and seen == ["outer"]
    assert actual_interval == interval
    assert (0 < delay <= interval) if interval else delay == 0
    signals.setitimer(signals.ITIMER_REAL, 0)
    return {"case": "outer", "interval": interval, "delay": delay, "seen": seen}


def returning_case():
    signals: Any = signal
    seen = []

    def handler(_signum, _frame):
        seen.append("outer")

    signals.signal(signals.SIGALRM, handler)
    signals.setitimer(signals.ITIMER_REAL, 0.025, 0.025)
    error = budget.RouteDeadlineExhausted("inner", 2, 0.16, 0)
    try:
        bounded(0.16, lambda: time.sleep(1), error)
    except budget.RouteDeadlineExhausted as caught:
        assert caught is error
    else:
        raise AssertionError("returning outer handler removed the inner bound")
    assert seen and signals.getsignal(signals.SIGALRM) is handler
    delay, interval = signals.getitimer(signals.ITIMER_REAL)
    signals.setitimer(signals.ITIMER_REAL, 0)
    assert 0 < delay <= 0.025 and interval == 0.025
    return {"case": "returning-periodic", "count": len(seen), "delay": delay}


def nested_case():
    outer = budget.RouteDeadlineExhausted("outer", 1, 0.03, 0)
    inner = budget.RouteDeadlineExhausted("inner", 2, 0.3, 0)
    try:
        bounded(0.03, lambda: bounded(0.3, lambda: time.sleep(1), inner), outer)
    except budget.RouteDeadlineExhausted as caught:
        assert caught is outer
    else:
        raise AssertionError("nested outer budget was postponed")
    return {"case": "nested", "stage": outer.blocking_stage}


def benchmark_case():
    inner = budget.RouteDeadlineExhausted("inner", 2, 0.3, 0)
    try:
        run_with_route_timeout(0.03, lambda: bounded(0.3, lambda: time.sleep(1), inner))
    except RouteExecutionTimeout as caught:
        assert caught.seconds == 0.03
    else:
        raise AssertionError("actual benchmark outer timeout was lost")
    return {"case": "benchmark", "exception": "RouteExecutionTimeout"}


def main():
    assert sys.platform.startswith("linux")
    signals: Any = signal
    original = signals.getsignal(signals.SIGALRM)
    try:
        records = [
            outer_case(0),
            outer_case(0.5),
            returning_case(),
            nested_case(),
            benchmark_case(),
        ]
        assert signals.getitimer(signals.ITIMER_REAL) == (0, 0)
        print(
            json.dumps(
                {
                    "platform": sys.platform,
                    "records": records,
                    "owned_timers_cleared": True,
                }
            )
        )
    finally:
        signals.setitimer(signals.ITIMER_REAL, 0)
        signals.signal(signals.SIGALRM, original)


if __name__ == "__main__":
    main()
