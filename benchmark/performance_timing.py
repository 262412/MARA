from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any


def measure_duration(call: Callable[[], Any]) -> float:
    started_at = perf_counter()
    call()
    return perf_counter() - started_at


def add_amortized_preparation_timing(
    prediction: dict[str, Any],
    preparation_seconds: float,
    example_count: int,
) -> None:
    amortized = preparation_seconds / example_count if example_count else 0.0
    performance = dict(prediction.get("performance") or {})
    total = float(performance.get("total_seconds") or 0.0)
    performance["preparation_seconds_amortized"] = round(amortized, 4)
    performance["total_seconds_including_preparation"] = round(
        total + amortized,
        4,
    )
    prediction["performance"] = performance


def apply_engine_failure_diagnostics(
    prediction: dict[str, Any],
    engine: Any,
) -> None:
    diagnostics_fn = getattr(engine, "route_timeout_diagnostics", None)
    if not callable(diagnostics_fn):
        return
    diagnostics = diagnostics_fn()
    if not isinstance(diagnostics, dict):
        return
    trace = diagnostics.get("retrieval_trace")
    if isinstance(trace, list):
        prediction["retrieval_trace"] = [
            dict(item) for item in trace if isinstance(item, dict)
        ]
    _merge_failure_timings(prediction, diagnostics.get("timings"))
    cache = diagnostics.get("cache")
    if isinstance(cache, dict):
        prediction["cache"] = {
            **dict(prediction.get("cache") or {}),
            **cache,
        }


def _merge_failure_timings(
    prediction: dict[str, Any],
    timings: Any,
) -> None:
    if not isinstance(timings, dict):
        return
    prediction_timings = dict(prediction.get("timings") or {})
    prediction_timings.update(
        {
            key: round(float(value), 4)
            for key, value in timings.items()
            if key
            in {
                "parse_seconds",
                "index_seconds",
                "retrieval_seconds",
                "generation_seconds",
            }
            and value is not None
        }
    )
    prediction["timings"] = prediction_timings
    performance = dict(prediction.get("performance") or {})
    performance.update(prediction_timings)
    performance["total_seconds"] = round(sum(prediction_timings.values()), 4)
    prediction["performance"] = performance
