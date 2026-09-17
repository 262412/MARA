"""Execute bounded calls with the existing signal or owned worker mechanism.

These operations install timers or start threads. Request budgets, cancellation
selection and trace ownership stay with the caller.
"""

from __future__ import annotations

from logging import Logger
from typing import Any, Callable, TypeVar

_T = TypeVar("_T")


def run_signal_timeout(
    timeout_seconds: float,
    call: Callable[[], _T],
    *,
    on_timeout: Callable[[], Exception],
    monotonic: Callable[[], float],
    get_handler: Callable[[], Any],
    get_timer: Callable[[], tuple[float, float]],
    set_handler: Callable[[Any], Any],
    set_timer: Callable[..., Any],
) -> _T:
    previous_handler = get_handler()
    previous_delay, previous_interval = get_timer()
    started = monotonic()

    def handle_timeout(_signum: int, _frame: Any) -> None:
        raise on_timeout()

    set_handler(handle_timeout)
    set_timer(max(0.000001, float(timeout_seconds)))
    try:
        return call()
    finally:
        set_timer(0.0)
        set_handler(previous_handler)
        if previous_delay > 0:
            elapsed = monotonic() - started
            set_timer(max(0.000001, previous_delay - elapsed), previous_interval)


def run_worker_timeout(
    timeout_seconds: float,
    call: Callable[[], _T],
    *,
    on_timeout: Callable[[], Exception],
    on_cancel: Callable[[], None],
    on_stopped: Callable[[bool], None],
    make_event: Callable[[], Any],
    make_lock: Callable[[], Any],
    make_thread: Callable[..., Any],
    logger: Logger,
) -> _T:
    completed = make_event()
    result_lock = make_lock()
    accepting_result = True
    result: list[_T] = []
    errors: list[BaseException] = []

    def invoke() -> None:
        try:
            value = call()
        except Exception as error:
            logger.debug("DocQA route worker failed", exc_info=True)
            with result_lock:
                if accepting_result:
                    errors.append(error)
        else:
            with result_lock:
                if accepting_result:
                    result.append(value)
        finally:
            completed.set()

    worker = make_thread(target=invoke, name="mara-route-stage", daemon=True)
    worker.start()
    if not completed.wait(max(0.000001, float(timeout_seconds))):
        with result_lock:
            accepting_result = False
            result.clear()
            errors.clear()
        on_cancel()
        on_stopped(completed.wait(0.1))
        raise on_timeout()
    if errors:
        raise errors[0]
    return result[0]
