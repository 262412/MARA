from __future__ import annotations

from time import perf_counter
from typing import Any, Callable, TypeVar

from .evidence_schema import EvidenceBundle

_T = TypeVar("_T")
_PIPELINE_TIMING_KEYS = (
    "planning_seconds",
    "retrieval_seconds",
    "generation_seconds",
    "retry_seconds",
    "verification_seconds",
    "finalization_seconds",
)


class PipelineStageTimings:
    def __init__(self) -> None:
        self.values = {key: 0.0 for key in _PIPELINE_TIMING_KEYS}

    def measure(
        self,
        key: str,
        call: Callable[..., _T],
        *args: Any,
        **kwargs: Any,
    ) -> _T:
        started = perf_counter()
        try:
            return call(*args, **kwargs)
        finally:
            self.values[key] += perf_counter() - started

    def record(self, bundle: EvidenceBundle) -> None:
        bundle.metadata["pipeline_stage_timings"] = {
            key: round(max(0.0, float(value)), 6)
            for key, value in self.values.items()
        }
