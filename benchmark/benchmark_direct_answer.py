from __future__ import annotations

from typing import Any

from .engine_result import EngineRunResult
from .engines import BaseBenchmarkEngine
from .schemas import BenchmarkDocument


class BenchmarkDirectAnswerEngine(BaseBenchmarkEngine):
    name = "benchmark_direct_answer"

    def run(
        self,
        *,
        example: Any,
        documents: list[BenchmarkDocument],
    ) -> EngineRunResult:
        del documents
        (
            answer,
            _evidence,
            generation_seconds,
            evidence_metadata,
        ) = self._generate_from_context(example, "")
        timings = {"generation_seconds": round(generation_seconds, 4)}
        return EngineRunResult(
            answer=answer,
            timings=timings,
            context_preview="",
            evidence_metadata=evidence_metadata,
            retrieval_trace=[
                {
                    "engine": self.name,
                    "selection": "no_retrieval",
                    "context_characters": 0,
                }
            ],
        )
