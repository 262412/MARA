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
    configured: bool = False,
    loaded: bool = False,
    failure_reason: str = "",
    model: str = "",
    input_identities: list[str] | None = None,
    output_identities: list[str] | None = None,
) -> dict[str, object]:
    return {
        "candidate_stage": "post_fusion",
        "candidate_limit": candidate_limit,
        "candidate_input_count": input_count,
        "input_count": input_count,
        "output_limit": output_limit,
        "output_count": output_count,
        "backend_execution": backend_execution,
        "configured": configured,
        "loaded": loaded,
        "executed": backend_execution,
        "backend": backend,
        "model": model,
        "score_field": score_field,
        "input_identities": list(input_identities or []),
        "output_identities": list(output_identities or []),
        "failure_reason": failure_reason,
    }


def materialize_reranked_candidates(
    candidates: list[dict[str, Any]],
    evidence_metadata: dict[str, Any],
    *,
    limit: int,
) -> tuple[list[dict[str, Any]] | None, dict[str, object]]:
    explicit_trace = evidence_metadata.get("reranker_execution_trace")
    if isinstance(explicit_trace, dict):
        return _materialize_from_execution_trace(
            candidates,
            explicit_trace,
            limit=limit,
        )
    backend = str(
        evidence_metadata.get("reranker_backend")
        or evidence_metadata.get("reranking_backend")
        or _uniform_item_backend(candidates)
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
            configured=bool(backend),
            loaded=bool(backend),
            failure_reason="missing_complete_execution_trace",
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
        configured=True,
        loaded=True,
        input_identities=[_item_input_identity(item) for item in candidates],
        output_identities=[_item_input_identity(item) for item in output],
    )


def _materialize_from_execution_trace(
    candidates: list[dict[str, Any]],
    trace: dict[str, Any],
    *,
    limit: int,
) -> tuple[list[dict[str, Any]] | None, dict[str, object]]:
    configured = bool(trace.get("configured"))
    loaded = bool(trace.get("loaded"))
    executed = bool(trace.get("executed"))
    input_identities = [
        str(value).strip()
        for value in trace.get("input_identities") or []
        if str(value).strip()
    ]
    output_identities = [
        str(value).strip()
        for value in trace.get("output_identities") or []
        if str(value).strip()
    ]
    backend = str(trace.get("backend") or "").strip()
    model = str(trace.get("model") or "").strip()
    score_field = str(trace.get("score_field") or "reranker_score").strip()
    if not executed:
        return None, ranking_trace(
            candidate_limit=len(candidates),
            input_count=int(trace.get("input_count") or len(input_identities)),
            output_count=0,
            backend_execution=False,
            backend=backend,
            model=model,
            score_field=score_field,
            output_limit=limit,
            configured=configured,
            loaded=loaded,
            failure_reason=str(trace.get("failure_reason") or "not_executed"),
            input_identities=input_identities,
            output_identities=output_identities,
        )
    input_set = set(input_identities)
    scored = [
        (_reranking_score(item), index, item)
        for index, item in enumerate(candidates)
        if _reranking_score(item) is not None
        and (
            not input_set
            or _item_input_identity(item) in input_set
            or str(item.get("canonical_id") or "") in input_set
        )
    ]
    scored.sort(key=lambda row: (-float(row[0] or 0.0), row[1]))
    output = [item for _score, _index, item in scored[:limit]]
    return output, ranking_trace(
        candidate_limit=len(candidates),
        input_count=int(trace.get("input_count") or len(input_identities)),
        output_count=len(output),
        backend_execution=True,
        backend=backend,
        model=model,
        score_field=score_field,
        output_limit=limit,
        configured=configured,
        loaded=loaded,
        failure_reason=(
            "" if output else str(trace.get("failure_reason") or "no_scored_output")
        ),
        input_identities=input_identities,
        output_identities=output_identities,
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


def _uniform_item_backend(candidates: list[dict[str, Any]]) -> str:
    backends = {
        str(
            dict(item.get("metadata") or {}).get("reranker_backend")
            or item.get("reranker_backend")
            or ""
        ).strip()
        for item in candidates
    }
    backends.discard("")
    return next(iter(backends)) if len(backends) == 1 else ""


def _item_input_identity(item: dict[str, Any]) -> str:
    metadata = dict(item.get("metadata") or {})
    return str(
        item.get("reranker_input_identity")
        or metadata.get("reranker_input_identity")
        or item.get("canonical_id")
        or item.get("evidence_id")
        or ""
    ).strip()


def actual_reranker_input(
    candidates: list[dict[str, Any]],
    trace: dict[str, object],
) -> list[dict[str, Any]]:
    raw_identities = trace.get("input_identities")
    identity_values = (
        raw_identities if isinstance(raw_identities, (list, tuple, set)) else []
    )
    identities = {str(value).strip() for value in identity_values if str(value).strip()}
    if not identities:
        return candidates if "configured" not in trace else []
    return [item for item in candidates if _item_input_identity(item) in identities]
