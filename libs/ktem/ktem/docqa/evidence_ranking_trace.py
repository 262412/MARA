from __future__ import annotations

from typing import Any


def ranking_trace(
    *,
    candidate_limit: int,
    input_count: int,
    output_count: int,
    backend_execution: bool = False,
    backend: str = "",
    score_field: str = "",
    output_limit: int = 0,
) -> dict[str, object]:
    return {
        "candidate_stage": "post_fusion",
        "candidate_limit": candidate_limit,
        "candidate_input_count": input_count,
        "output_limit": output_limit,
        "output_count": output_count,
        "backend_execution": backend_execution,
        "backend": backend,
        "score_field": score_field,
    }


def materialize_reranked_candidates(
    candidates: list[dict[str, Any]],
    evidence_metadata: dict[str, Any],
    *,
    limit: int,
) -> tuple[list[dict[str, Any]] | None, dict[str, object]]:
    backend = str(
        evidence_metadata.get("reranker_backend")
        or evidence_metadata.get("reranking_backend")
        or ""
    ).strip()
    scored = [
        (_reranking_score(item), index, item) for index, item in enumerate(candidates)
    ]
    score_field = _reranking_score_field(candidates)
    executed = bool(
        candidates
        and backend
        and score_field
        and all(score is not None for score, _index, _item in scored)
    )
    if not executed:
        return None, ranking_trace(
            candidate_limit=len(candidates),
            input_count=len(candidates),
            output_count=0,
            backend_execution=False,
            output_limit=limit,
        )
    scored.sort(key=lambda row: (-float(row[0] or 0.0), row[1]))
    output = [item for _score, _index, item in scored[:limit]]
    return output, ranking_trace(
        candidate_limit=len(candidates),
        input_count=len(candidates),
        output_count=len(output),
        backend_execution=True,
        backend=backend,
        score_field=score_field,
        output_limit=limit,
    )


def _reranking_score(item: dict[str, Any]) -> float | None:
    metadata = dict(item.get("metadata") or {})
    for field in ("reranking_score", "reranker_score"):
        value = metadata.get(field)
        if value is None:
            value = item.get(field)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _reranking_score_field(candidates: list[dict[str, Any]]) -> str:
    for field in ("reranking_score", "reranker_score"):
        if all(
            item.get(field) is not None
            or dict(item.get("metadata") or {}).get(field) is not None
            for item in candidates
        ):
            return field
    return ""
