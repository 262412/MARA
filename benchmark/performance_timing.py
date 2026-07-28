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


def record_stage_timing(
    prediction: dict[str, Any],
    key: str,
    seconds: float,
) -> None:
    value = round(max(0.0, float(seconds)), 6)
    timings = dict(prediction.get("timings") or {})
    timings[key] = value
    prediction["timings"] = timings
    performance = dict(prediction.get("performance") or {})
    performance[key] = value
    prediction["performance"] = performance


def runtime_timing_payload(
    evidence_metadata: dict[str, Any],
    *,
    index_seconds: float,
    runtime_turn_seconds: float,
    grounding_seconds: float,
) -> tuple[dict[str, float], dict[str, float]]:
    pipeline_stage_timings = dict(evidence_metadata.get("pipeline_stage_timings") or {})
    segmented = {
        f"pipeline_{key}": float(value)
        for key, value in pipeline_stage_timings.items()
        if key.endswith("_seconds")
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    }
    timings = {
        "index_seconds": index_seconds,
        "runtime_turn_seconds": runtime_turn_seconds,
        "generation_seconds": segmented.get("pipeline_generation_seconds", 0.0),
        "answer_grounding_seconds": grounding_seconds,
        **segmented,
    }
    performance = {
        **timings,
        "total_seconds": round(
            index_seconds + runtime_turn_seconds + grounding_seconds,
            4,
        ),
    }
    return timings, performance


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
                "runtime_turn_seconds",
            }
            and value is not None
        }
    )
    prediction["timings"] = prediction_timings
    performance = dict(prediction.get("performance") or {})
    performance.update(prediction_timings)
    performance["total_seconds"] = round(sum(prediction_timings.values()), 4)
    prediction["performance"] = performance
