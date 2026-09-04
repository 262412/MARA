from __future__ import annotations

import signal
from collections.abc import Callable
from time import perf_counter
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
    sigalrm = getattr(signal, "SIGALRM", None)
    setitimer = getattr(signal, "setitimer", None)
    itimer_real = getattr(signal, "ITIMER_REAL", None)
    if sigalrm is None or setitimer is None or itimer_real is None:
        return call()

    def _handle_timeout(_signum, _frame):
        raise RouteExecutionTimeout(float(timeout_seconds))

    previous_handler = signal.getsignal(sigalrm)
    signal.signal(sigalrm, _handle_timeout)
    setitimer(itimer_real, float(timeout_seconds))
    try:
        return call()
    finally:
        setitimer(itimer_real, 0)
        signal.signal(sigalrm, previous_handler)


def raise_if_route_budget_exceeded(
    started_at: float,
    timeout_seconds: float | None,
) -> None:
    if timeout_seconds and perf_counter() - started_at > timeout_seconds:
        raise RouteExecutionTimeout(timeout_seconds)


def route_timeout_seconds(
    exc: Exception,
    configured_seconds: float | None,
) -> float | None:
    if isinstance(exc, RouteExecutionTimeout):
        return exc.seconds
    return configured_seconds
