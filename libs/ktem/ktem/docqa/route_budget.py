from __future__ import annotations

import logging
import signal
import threading
from dataclasses import dataclass
from time import monotonic
from typing import Any, Callable, TypeVar

DEFAULT_OPTIONAL_STAGE_RESERVE_SECONDS = 12.0
DEFAULT_TERMINAL_COMMIT_RESERVE_SECONDS = 12.0

_T = TypeVar("_T")
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RouteDeadlineExhausted(TimeoutError):
    blocking_stage: str
    absolute_deadline_monotonic: float
    call_timeout_budget_seconds: float
    remaining_route_seconds: float

    def __str__(self) -> str:
        return (
            f"Route deadline exhausted during {self.blocking_stage} after "
            f"{self.call_timeout_budget_seconds:.4f} seconds."
        )


def remaining_route_seconds(request: Any) -> float | None:
    deadline = getattr(request, "route_deadline_monotonic", None)
    if deadline is None or deadline == "":
        return None
    return max(0.0, float(deadline) - monotonic())


def optional_stage_allowed(
    request: Any,
    *,
    reserve_seconds: float = DEFAULT_OPTIONAL_STAGE_RESERVE_SECONDS,
) -> bool:
    remaining = remaining_route_seconds(request)
    required_remaining = optional_stage_reserve_seconds(
        request,
        minimum_seconds=reserve_seconds,
    ) + terminal_commit_reserve_seconds(request)
    return remaining is None or remaining > required_remaining


def optional_stage_reserve_seconds(
    request: Any,
    *,
    minimum_seconds: float = DEFAULT_OPTIONAL_STAGE_RESERVE_SECONDS,
) -> float:
    completed_costs = [
        float(event.get("elapsed_seconds") or 0.0)
        for event in _budget_trace(request)
        if event.get("status") == "completed"
    ]
    return max([max(0.0, float(minimum_seconds)), *completed_costs])


def terminal_commit_reserve_seconds(request: Any) -> float:
    value = getattr(request, "route_terminal_reserve_seconds", None)
    if value in (None, ""):
        return DEFAULT_TERMINAL_COMMIT_RESERVE_SECONDS
    return max(0.0, float(str(value)))


def route_call_timeout_seconds(
    request: Any,
    *,
    configured_timeout_seconds: float | None = None,
) -> float | None:
    remaining = remaining_route_seconds(request)
    if remaining is None:
        return (
            max(0.0, float(configured_timeout_seconds))
            if configured_timeout_seconds is not None
            else None
        )
    available = max(0.0, remaining - terminal_commit_reserve_seconds(request))
    if configured_timeout_seconds is None:
        return available
    return min(available, max(0.0, float(configured_timeout_seconds)))


def run_blocking_route_stage(
    request: Any,
    blocking_stage: str,
    call: Callable[..., _T],
    *args: Any,
    configured_timeout_seconds: float | None = None,
    **kwargs: Any,
) -> _T:
    """Run one blocking runtime call inside the shared absolute route budget.

    On POSIX main-thread execution this temporarily shortens the process alarm
    while preserving the benchmark's outer alarm.  Other execution contexts
    still receive the cooperative timeout on the request, and the pre/post
    deadline checks remain fail-closed.
    """

    request.route_last_blocking_stage = blocking_stage
    absolute_deadline = _absolute_deadline(request)
    if absolute_deadline is None and configured_timeout_seconds is None:
        try:
            return call(*args, **kwargs)
        except Exception:
            request.route_failed_stage = blocking_stage
            LOGGER.exception("DocQA route stage failed: %s", blocking_stage)
            raise
    remaining_before = remaining_route_seconds(request)
    timeout = route_call_timeout_seconds(
        request,
        configured_timeout_seconds=configured_timeout_seconds,
    )
    event = _route_budget_event(
        request,
        blocking_stage,
        absolute_deadline,
        remaining_before,
        configured_timeout_seconds,
        timeout,
    )
    _budget_trace(request).append(event)
    if timeout is not None and timeout <= 0:
        event["status"] = "deadline_exhausted_before_call"
        raise _deadline_error(request, blocking_stage, timeout, remaining_before)

    previous_call_timeout = getattr(request, "route_call_timeout_seconds", None)
    request.route_call_timeout_seconds = timeout
    cancel_event = threading.Event()
    request.route_call_cancel_event = cancel_event
    started = monotonic()
    try:
        return _run_timed_route_stage(
            request,
            blocking_stage,
            call,
            args,
            kwargs,
            timeout,
            cancel_event,
            event,
        )
    except RouteDeadlineExhausted:
        event["status"] = "deadline_exhausted"
        raise
    except Exception as error:
        event["status"] = "failed"
        event["error_type"] = type(error).__name__
        request.route_failed_stage = blocking_stage
        LOGGER.exception("DocQA timed route stage failed: %s", blocking_stage)
        raise
    finally:
        event["elapsed_seconds"] = round(max(0.0, monotonic() - started), 6)
        event["remaining_route_seconds_after"] = _rounded(
            remaining_route_seconds(request)
        )
        if previous_call_timeout is None:
            try:
                delattr(request, "route_call_timeout_seconds")
            except AttributeError:
                pass
        else:
            request.route_call_timeout_seconds = previous_call_timeout


def _route_budget_event(
    request: Any,
    blocking_stage: str,
    absolute_deadline: float | None,
    remaining_before: float | None,
    configured_timeout_seconds: float | None,
    timeout: float | None,
) -> dict[str, Any]:
    return {
        "stage": "route_budget",
        "blocking_stage": blocking_stage,
        "absolute_deadline_monotonic": absolute_deadline,
        "remaining_route_seconds_before": _rounded(remaining_before),
        "terminal_commit_reserve_seconds": terminal_commit_reserve_seconds(request),
        "configured_call_timeout_seconds": configured_timeout_seconds,
        "call_timeout_budget_seconds": _rounded(timeout),
        "status": "started",
    }


def _run_timed_route_stage(
    request: Any,
    blocking_stage: str,
    call: Callable[..., _T],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    timeout: float | None,
    cancel_event: threading.Event,
    event: dict[str, Any],
) -> _T:
    result = _run_with_interruptible_timeout(
        timeout,
        lambda: call(*args, **kwargs),
        on_timeout=lambda: _deadline_error(
            request,
            blocking_stage,
            timeout,
            remaining_route_seconds(request),
        ),
        on_cancel=lambda: _cancel_blocking_route_stage(
            request,
            blocking_stage,
            call,
            cancel_event,
        ),
        event=event,
    )
    if remaining_route_seconds(request) == 0.0:
        raise _deadline_error(
            request,
            blocking_stage,
            timeout,
            remaining_route_seconds(request),
        )
    event["status"] = "completed"
    return result


def route_budget_trace(request: Any) -> list[dict[str, Any]]:
    return [dict(event) for event in _budget_trace(request)]


def deadline_trace_event(
    request: Any,
    error: RouteDeadlineExhausted,
) -> dict[str, Any]:
    return {
        "stage": "route_deadline",
        "blocking_stage": error.blocking_stage,
        "absolute_deadline_monotonic": error.absolute_deadline_monotonic,
        "call_timeout_budget_seconds": round(
            max(0.0, error.call_timeout_budget_seconds), 6
        ),
        "remaining_route_seconds": round(max(0.0, error.remaining_route_seconds), 6),
        "stop_reason": "route_deadline_exhausted",
    }


def route_budget_metadata(request: Any) -> dict[str, Any]:
    remaining = remaining_route_seconds(request)
    return {
        "route_timeout_seconds": getattr(request, "route_timeout_seconds", None),
        "remaining_route_seconds": (
            round(remaining, 4) if remaining is not None else None
        ),
        "absolute_deadline_monotonic": _absolute_deadline(request),
        "terminal_commit_reserve_seconds": terminal_commit_reserve_seconds(request),
        "optional_stage_reserve_seconds": optional_stage_reserve_seconds(request),
    }


def _run_with_interruptible_timeout(
    timeout_seconds: float | None,
    call: Callable[[], _T],
    *,
    on_timeout: Callable[[], RouteDeadlineExhausted],
    on_cancel: Callable[[], None],
    event: dict[str, Any],
) -> _T:
    if timeout_seconds is None:
        return call()
    if not _signal_timeout_available():
        return _run_with_worker_timeout(
            timeout_seconds,
            call,
            on_timeout=on_timeout,
            on_cancel=on_cancel,
            event=event,
        )
    sigalrm = signal.SIGALRM
    itimer_real = signal.ITIMER_REAL
    previous_handler = signal.getsignal(sigalrm)
    previous_delay, previous_interval = signal.getitimer(itimer_real)
    started = monotonic()

    def handle_timeout(_signum: int, _frame: Any) -> None:
        raise on_timeout()

    signal.signal(sigalrm, handle_timeout)
    signal.setitimer(itimer_real, max(0.000001, float(timeout_seconds)))
    try:
        return call()
    finally:
        signal.setitimer(itimer_real, 0.0)
        signal.signal(sigalrm, previous_handler)
        if previous_delay > 0:
            elapsed = monotonic() - started
            signal.setitimer(
                itimer_real,
                max(0.000001, previous_delay - elapsed),
                previous_interval,
            )


def _run_with_worker_timeout(
    timeout_seconds: float,
    call: Callable[[], _T],
    *,
    on_timeout: Callable[[], RouteDeadlineExhausted],
    on_cancel: Callable[[], None],
    event: dict[str, Any],
) -> _T:
    completed = threading.Event()
    result: list[_T] = []
    errors: list[BaseException] = []

    def invoke() -> None:
        try:
            result.append(call())
        except Exception as error:
            LOGGER.debug("DocQA route worker failed", exc_info=error)
            errors.append(error)
        finally:
            completed.set()

    worker = threading.Thread(
        target=invoke,
        name="mara-route-stage",
        daemon=True,
    )
    worker.start()
    if not completed.wait(max(0.000001, float(timeout_seconds))):
        on_cancel()
        producer_stopped = completed.wait(0.1)
        event["cancellation_status"] = (
            "producer_stopped" if producer_stopped else "producer_unresponsive"
        )
        raise on_timeout()
    if errors:
        raise errors[0]
    return result[0]


def _cancel_blocking_route_stage(
    request: Any,
    blocking_stage: str,
    call: Callable[..., Any],
    cancel_event: threading.Event,
) -> None:
    cancel_event.set()
    callback = getattr(request, "route_cancel_callback", None)
    if callable(callback):
        callback(blocking_stage)
    owner = getattr(call, "__self__", None)
    cancel = getattr(owner, "cancel", None)
    if callable(cancel):
        cancel()


def _signal_timeout_available() -> bool:
    return bool(
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
        and hasattr(signal, "ITIMER_REAL")
        and hasattr(signal, "setitimer")
        and hasattr(signal, "getitimer")
    )


def _deadline_error(
    request: Any,
    blocking_stage: str,
    timeout: float | None,
    remaining: float | None,
) -> RouteDeadlineExhausted:
    return RouteDeadlineExhausted(
        blocking_stage=blocking_stage,
        absolute_deadline_monotonic=_absolute_deadline(request) or monotonic(),
        call_timeout_budget_seconds=max(0.0, float(timeout or 0.0)),
        remaining_route_seconds=max(0.0, float(remaining or 0.0)),
    )


def _absolute_deadline(request: Any) -> float | None:
    value = getattr(request, "route_deadline_monotonic", None)
    return None if value in (None, "") else float(str(value))


def _budget_trace(request: Any) -> list[dict[str, Any]]:
    trace = getattr(request, "route_budget_trace", None)
    if isinstance(trace, list):
        return trace
    trace = []
    request.route_budget_trace = trace
    return trace


def _rounded(value: float | None) -> float | None:
    return round(max(0.0, value), 6) if value is not None else None
