from __future__ import annotations

from typing import Any

from . import controller_fields as cf
from .engine_result import EngineRunResult


def prediction_to_result(prediction: dict[str, Any]) -> EngineRunResult:
    return EngineRunResult(
        answer=str(prediction.get("predicted_answer") or ""),
        predicted_pages=list(prediction.get("predicted_pages") or []),
        predicted_sources=list(prediction.get("predicted_sources") or []),
        predicted_citations=list(prediction.get("predicted_citations") or []),
        predicted_element_ids=list(prediction.get("predicted_element_ids") or []),
        retrieved_hits=list(prediction.get("retrieved_hits") or []),
        timings=dict(prediction.get("timings") or {}),
        performance=dict(prediction.get("performance") or {}),
        cache=dict(prediction.get("cache") or {}),
        cost=dict(prediction.get("cost") or {}),
        context_preview=str(prediction.get("context_preview") or ""),
        retrieval_trace=list(prediction.get("retrieval_trace") or []),
        agent_trace=list(prediction.get("agent_trace") or []),
        evidence_metadata=dict(prediction.get("evidence_metadata") or {}),
        **cf.controller_prediction_kwargs(prediction),
        claim_verification=dict(prediction.get("claim_verification") or {}),
        presentation=dict(prediction.get("presentation") or {}),
    )
