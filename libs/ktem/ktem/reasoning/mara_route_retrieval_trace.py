from __future__ import annotations

from typing import Any


def reranker_execution_traces(pipeline: Any) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for retriever in getattr(pipeline, "retrievers", None) or []:
        vector_retrieval = getattr(retriever, "vector_retrieval", None)
        last_trace = getattr(vector_retrieval, "last_trace", None)
        metadata = (
            dict(last_trace.get("metadata") or {})
            if isinstance(last_trace, dict)
            else {}
        )
        trace = metadata.get("reranker_execution")
        if isinstance(trace, dict):
            traces.append(dict(trace))
    return traces


def bounded_retrieval_attempts(attempts: Any) -> list[dict[str, Any]]:
    return [
        {
            "attempt": int(attempt.get("attempt") or 0),
            "evidence_count": int(attempt.get("evidence_count") or 0),
            "retry_reason": str(attempt.get("retry_reason") or ""),
        }
        for attempt in attempts or []
        if isinstance(attempt, dict)
    ]
