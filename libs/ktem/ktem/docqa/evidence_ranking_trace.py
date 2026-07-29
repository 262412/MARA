from __future__ import annotations

from typing import Any

from .evidence_identity import identity_of


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
    backend_output_count: int | None = None,
    backend_output_identities: list[str] | None = None,
    scored_count: int | None = None,
) -> dict[str, object]:
    return {
        "candidate_stage": "post_fusion",
        "candidate_limit": candidate_limit,
        "candidate_input_count": input_count,
        "input_count": input_count,
        "reranker_input_count": input_count,
        "reranker_scored_count": (
            input_count
            if scored_count is None and backend_execution
            else scored_count or 0
        ),
        "output_limit": output_limit,
        "output_count": output_count,
        "backend_output_count": (
            output_count if backend_output_count is None else backend_output_count
        ),
        "reranker_output_count": output_count,
        "reranker_artifact_record_count": output_count,
        "selection_retained_reranked_count": None,
        "backend_execution": backend_execution,
        "configured": configured,
        "loaded": loaded,
        "executed": backend_execution,
        "backend": backend,
        "model": model,
        "score_field": score_field,
        "input_identities": list(input_identities or []),
        "output_identities": list(output_identities or []),
        "backend_output_identities": list(
            backend_output_identities
            if backend_output_identities is not None
            else output_identities or []
        ),
        "failure_reason": failure_reason,
    }


def materialize_reranked_candidates(
    candidates: list[dict[str, Any]],
    evidence_metadata: dict[str, Any],
    *,
    limit: int,
) -> tuple[list[dict[str, Any]] | None, dict[str, object]]:
    execution_traces = [
        dict(trace)
        for trace in evidence_metadata.get("reranker_execution_traces") or []
        if isinstance(trace, dict)
    ]
    if execution_traces:
        return _materialize_from_execution_traces(
            candidates,
            execution_traces,
            limit=limit,
        )
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
    output = _dedupe_ranked(output)
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
        backend_output_count=len(scored[:limit]),
        scored_count=len(scored),
    )


def _materialize_from_execution_traces(
    candidates: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    *,
    limit: int,
) -> tuple[list[dict[str, Any]] | None, dict[str, object]]:
    context = _execution_trace_context(traces)
    executed_traces = context["executed_traces"]
    if not executed_traces:
        return None, _not_executed_query_trace(
            candidates,
            traces,
            context,
            limit=limit,
        )
    by_identity, observations = _candidate_observations(
        candidates,
        executed_traces,
    )
    output = _observed_reranker_output(by_identity, observations, limit=limit)
    return output, _executed_query_trace(
        candidates,
        traces,
        context,
        output,
        limit=limit,
    )


def _candidate_observations(
    candidates: list[dict[str, Any]],
    executed_traces: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    by_identity: dict[str, dict[str, Any]] = {}
    observations: dict[str, list[dict[str, Any]]] = {}
    for trace in executed_traces:
        accepted_ids = set(_trace_values(trace, "output_identities"))
        accepted_ids.update(
            [] if accepted_ids else _trace_values(trace, "input_identities")
        )
        for candidate in candidates:
            raw_identity = _item_input_identity(candidate)
            canonical_identity = identity_of(candidate).key
            if accepted_ids and not (
                _candidate_trace_aliases(candidate) & accepted_ids
            ):
                continue
            score = _reranking_score(candidate)
            if score is None:
                continue
            observations.setdefault(canonical_identity, []).append(
                _reranker_observation(trace, raw_identity, score)
            )
            existing = by_identity.get(canonical_identity)
            if existing is None or float(_reranking_score(existing) or 0.0) < score:
                by_identity[canonical_identity] = dict(candidate)
    return by_identity, observations


def _observed_reranker_output(
    by_identity: dict[str, dict[str, Any]],
    observations: dict[str, list[dict[str, Any]]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    ranked = sorted(
        by_identity.items(),
        key=lambda item: (
            -max(float(observation["score"]) for observation in observations[item[0]]),
            item[0],
        ),
    )
    output = []
    for canonical_identity, candidate in ranked[:limit]:
        candidate["reranker_observations"] = observations[canonical_identity]
        output.append(candidate)
    return output


def _executed_query_trace(
    candidates: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    context: dict[str, Any],
    output: list[dict[str, Any]],
    *,
    limit: int,
) -> dict[str, object]:
    executed_traces = context["executed_traces"]
    aggregate = ranking_trace(
        candidate_limit=len(candidates),
        input_count=sum(
            int(trace.get("input_count") or len(trace.get("input_identities") or []))
            for trace in executed_traces
        ),
        output_count=len(output),
        backend_execution=True,
        backend=_uniform_trace_value(executed_traces, "backend"),
        model=_uniform_trace_value(executed_traces, "model"),
        score_field=_uniform_trace_value(executed_traces, "score_field")
        or "reranker_score",
        output_limit=limit,
        configured=context["configured"],
        loaded=context["loaded"],
        input_identities=context["input_identities"],
        output_identities=[identity_of(item).key for item in output],
        backend_output_count=context["backend_output_total"],
        backend_output_identities=context["backend_output_identities"],
        scored_count=sum(
            int(trace.get("scored_count") or trace.get("input_count") or 0)
            for trace in executed_traces
        ),
    )
    aggregate.update(
        {
            "query_execution_count": len(executed_traces),
            "backend_output_total": context["backend_output_total"],
            "unique_output_identity_count": len(output),
            "reranker_artifact_record_count": len(output),
            "reranker_execution_traces": traces,
        }
    )
    return aggregate


def _execution_trace_context(
    traces: list[dict[str, Any]],
) -> dict[str, Any]:
    executed = [trace for trace in traces if bool(trace.get("executed"))]
    return {
        "executed_traces": executed,
        "configured": any(bool(trace.get("configured")) for trace in traces),
        "loaded": any(bool(trace.get("loaded")) for trace in traces),
        "input_identities": _trace_identities(traces, "input_identities"),
        "backend_output_identities": _trace_identities(
            executed,
            "output_identities",
        ),
        "backend_output_total": sum(
            int(
                trace.get("backend_output_count")
                or trace.get("output_count")
                or len(trace.get("output_identities") or [])
            )
            for trace in executed
        ),
    }


def _not_executed_query_trace(
    candidates: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    context: dict[str, Any],
    *,
    limit: int,
) -> dict[str, object]:
    trace = ranking_trace(
        candidate_limit=len(candidates),
        input_count=sum(int(item.get("input_count") or 0) for item in traces),
        output_count=0,
        backend_execution=False,
        output_limit=limit,
        configured=context["configured"],
        loaded=context["loaded"],
        failure_reason="reranker_not_executed",
        input_identities=context["input_identities"],
    )
    trace.update(
        {
            "query_execution_count": 0,
            "backend_output_total": 0,
            "unique_output_identity_count": 0,
            "reranker_artifact_record_count": 0,
            "reranker_execution_traces": traces,
        }
    )
    return trace


def _candidate_trace_aliases(candidate: dict[str, Any]) -> set[str]:
    return {
        _item_input_identity(candidate),
        identity_of(candidate).key,
        str(candidate.get("canonical_id") or "").strip(),
    }


def _reranker_observation(
    trace: dict[str, Any],
    raw_identity: str,
    score: float,
) -> dict[str, Any]:
    return {
        "query_id": str(trace.get("query_id") or ""),
        "slot_id": str(trace.get("slot_id") or ""),
        "round_id": int(trace.get("round_id") or 0),
        "backend": str(trace.get("backend") or ""),
        "model": str(trace.get("model") or ""),
        "input_identity": raw_identity,
        "score": score,
        "rank": _trace_rank(raw_identity, trace),
    }


def _trace_values(trace: dict[str, Any], field: str) -> list[str]:
    return [
        str(value).strip()
        for value in trace.get(field) or []
        if str(value or "").strip()
    ]


def _trace_identities(
    traces: list[dict[str, Any]],
    field: str,
) -> list[str]:
    return list(
        dict.fromkeys(
            str(value).strip()
            for trace in traces
            for value in trace.get(field) or []
            if str(value or "").strip()
        )
    )


def _trace_rank(identity: str, trace: dict[str, Any]) -> int | None:
    outputs = [
        str(value).strip()
        for value in trace.get("output_identities") or []
        if str(value or "").strip()
    ]
    return outputs.index(identity) + 1 if identity in outputs else None


def _uniform_trace_value(traces: list[dict[str, Any]], field: str) -> str:
    values = {
        str(trace.get(field) or "").strip()
        for trace in traces
        if str(trace.get(field) or "").strip()
    }
    return next(iter(values)) if len(values) == 1 else ""


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
    backend_output_count = int(
        trace.get("backend_output_count")
        or trace.get("output_count")
        or len(output_identities)
    )
    output = _dedupe_ranked([item for _score, _index, item in scored[:limit]])
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
        output_identities=[_item_input_identity(item) for item in output],
        backend_output_count=backend_output_count,
        backend_output_identities=output_identities,
        scored_count=len(scored),
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


def _dedupe_ranked(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        identity = identity_of(item).key
        if identity in seen:
            continue
        seen.add(identity)
        output.append(item)
    return output


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
