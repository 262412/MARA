from __future__ import annotations

from time import perf_counter
from typing import Any, Callable, Sequence

from kotaemon.base import RetrievedDocument

from .rankings import BaseReranking, LLMReranking


def execute_rerankers(
    rerankers: Sequence[BaseReranking],
    documents: list[RetrievedDocument],
    query: Any,
    *,
    rerank_top_k: int,
    output_top_k: int,
    filter_docs: Callable[
        [list[RetrievedDocument], int | None], list[RetrievedDocument]
    ],
) -> tuple[list[RetrievedDocument], dict[str, object], float]:
    trace = empty_reranker_trace(rerankers)
    if not rerankers or not query:
        return documents, trace, 0.0

    reranker_input = (
        filter_docs(documents, rerank_top_k) if rerank_top_k else list(documents)
    )
    trace.update(
        {
            "input_count": len(reranker_input),
            "input_identities": [retrieved_identity(item) for item in reranker_input],
        }
    )
    started_at = perf_counter()
    try:
        output = reranker_input
        for reranker in rerankers:
            if isinstance(reranker, LLMReranking):
                output = filter_docs(output, output_top_k)
            output = reranker.run(documents=output, query=query)
        trace.update(
            {
                "executed": True,
                "output_count": len(output),
                "output_identities": [retrieved_identity(item) for item in output],
                "failure_reason": "",
            }
        )
        stamp_reranker_output(output, trace)
        return output, trace, round((perf_counter() - started_at) * 1000, 3)
    except Exception as exc:
        trace["failure_reason"] = f"{type(exc).__name__}: {str(exc)}"
        raise


def empty_reranker_trace(
    rerankers: Sequence[BaseReranking],
) -> dict[str, object]:
    configured = bool(rerankers)
    backend = ",".join(dict.fromkeys(type(reranker).__name__ for reranker in rerankers))
    model = ",".join(
        dict.fromkeys(
            str(
                getattr(reranker, "model", None)
                or getattr(reranker, "model_name", None)
                or getattr(reranker, "endpoint", None)
                or type(reranker).__name__
            )
            for reranker in rerankers
        )
    )
    return {
        "configured": configured,
        "loaded": configured,
        "executed": False,
        "backend": backend,
        "model": model,
        "input_count": 0,
        "output_count": 0,
        "score_field": "reranker_score",
        "input_identities": [],
        "output_identities": [],
        "failure_reason": "" if configured else "not_configured",
    }


def retrieved_identity(document: RetrievedDocument) -> str:
    return str(getattr(document, "doc_id", "") or "").strip()


def stamp_reranker_output(
    documents: list[RetrievedDocument],
    trace: dict[str, object],
) -> None:
    for rank, document in enumerate(documents, start=1):
        metadata = dict(document.metadata or {})
        retrieval_metadata = dict(document.retrieval_metadata or {})
        score = metadata.get("reranking_score")
        if score is None:
            score = retrieval_metadata.get("reranking_score")
        if score is None:
            score = getattr(document, "score", None)
        fields = {
            "reranker_input_identity": retrieved_identity(document),
            "reranker_score": score,
            "reranker_rank": rank,
            "reranker_backend": trace.get("backend"),
            "reranker_model": trace.get("model"),
        }
        metadata.update(fields)
        metadata["reranker_execution_trace"] = dict(trace)
        retrieval_metadata.update(fields)
        document.metadata = metadata
        document.retrieval_metadata = retrieval_metadata
