from __future__ import annotations

import signal
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class RouteExecutionTimeout(TimeoutError):
    def __init__(self, seconds: float):
        self.seconds = seconds
        super().__init__(f"Route timed out after {seconds:g} seconds.")


def run_with_route_timeout(
    timeout_seconds: float | None,
    call: Callable[[], T],
) -> T:
    if not timeout_seconds or timeout_seconds <= 0:
        return call()

    def _handle_timeout(_signum, _frame):
        raise RouteExecutionTimeout(float(timeout_seconds))

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, float(timeout_seconds))
    try:
        return call()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
