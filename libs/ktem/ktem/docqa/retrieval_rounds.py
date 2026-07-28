from __future__ import annotations

from typing import Any, Callable

from .evidence import EvidenceBundle, build_evidence_bundle
from .evidence_identity import identity_of
from .query_planning import ensure_request_query_plan, request_planning_question
from .route_budget import optional_stage_allowed, route_budget_metadata

EvaluateFn = Callable[..., Any]
RetrieveFn = Callable[[Any, Any], dict[str, Any]]


def retrieve_with_rounds(
    request: Any,
    decision: Any,
    retrieve: RetrieveFn,
    *,
    evaluate: EvaluateFn,
    retry_poor: bool,
    max_rounds: int = 2,
) -> tuple[EvidenceBundle, Any]:
    plan = ensure_request_query_plan(request)
    evidence_metadata = _with_retrieval_lineage(
        retrieve(request, decision),
        round_id=1,
        query_id="round1:primary",
        slot_id="",
    )
    evidence_bundle = build_evidence_bundle(
        decision.legacy_route,
        request,
        evidence_metadata,
    )
    retrieve_decision = _evaluate(
        request,
        decision,
        evidence_bundle,
        evaluate,
        attempted_retry=False,
    )
    second_round_requests = _second_round_requests(evidence_bundle)
    retry_for_slots = bool(second_round_requests)
    retry_for_quality = (
        retrieve_decision.status == "ambiguous" and retrieve_decision.retry
    ) or (retrieve_decision.status == "poor" and retrieve_decision.retry and retry_poor)
    if retry_for_quality and not second_round_requests:
        second_round_requests = [_quality_retry_request(request)]
    if min(max_rounds, plan.max_retrieval_rounds) < 2 or (
        not retry_for_slots and not retry_for_quality
    ):
        return _with_retrieval_rounds(evidence_bundle, 1), retrieve_decision
    if not optional_stage_allowed(request):
        metadata = dict(evidence_bundle.metadata)
        metadata.update(route_budget_metadata(request))
        metadata["second_round_skipped_reason"] = "insufficient_remaining_time"
        evidence_bundle = EvidenceBundle(
            route=evidence_bundle.route,
            items=evidence_bundle.items,
            metadata=metadata,
        )
        return _with_retrieval_rounds(evidence_bundle, 1), retrieve_decision

    second_round_metadata = _retrieve_second_round(
        request,
        decision,
        retrieve,
        second_round_requests,
    )
    merged_metadata = _merge_retrieval_metadata(
        evidence_metadata,
        second_round_metadata,
    )
    evidence_bundle = build_evidence_bundle(
        decision.legacy_route,
        request,
        merged_metadata,
    )
    evidence_bundle = _with_retrieval_rounds(evidence_bundle, 2)
    retrieve_decision = _evaluate(
        request,
        decision,
        evidence_bundle,
        evaluate,
        attempted_retry=True,
    )
    return evidence_bundle, retrieve_decision


def _second_round_requests(bundle: EvidenceBundle) -> list[dict[str, str]]:
    requests = [
        dict(item)
        for item in bundle.metadata.get("second_round_requests") or []
        if isinstance(item, dict)
    ]
    if requests:
        return requests
    return [
        {
            "query_id": f"round2:legacy:{index}",
            "slot_id": "",
            "query": str(query),
            "modality": "auto",
        }
        for index, query in enumerate(
            bundle.metadata.get("second_round_queries") or [],
            start=1,
        )
    ]


def _quality_retry_request(request: Any) -> dict[str, str]:
    query = str(
        getattr(request, "retrieval_query", "")
        or request_planning_question(request)
        or getattr(request, "prompt", "")
        or ""
    ).strip()
    return {
        "query_id": "round2:quality_retry",
        "slot_id": "",
        "query": query,
        "modality": "auto",
    }


def _retrieve_second_round(
    request: Any,
    decision: Any,
    retrieve: RetrieveFn,
    requests: list[dict[str, str]],
) -> dict[str, Any]:
    original_query = str(getattr(request, "retrieval_query", "") or "")
    original_slot_id = str(getattr(request, "retrieval_slot_id", "") or "")
    original_round_id = int(getattr(request, "retrieval_round_id", 0) or 0)
    merged: dict[str, Any] = {}
    try:
        for retrieval_request in requests:
            request.retrieval_query = str(retrieval_request.get("query") or "")
            request.retrieval_slot_id = str(retrieval_request.get("slot_id") or "")
            request.retrieval_round_id = 2
            response = _with_retrieval_lineage(
                retrieve(request, decision),
                round_id=2,
                query_id=str(retrieval_request.get("query_id") or ""),
                slot_id=request.retrieval_slot_id,
            )
            merged = _merge_retrieval_metadata(merged, response)
        return merged
    finally:
        request.retrieval_query = original_query
        request.retrieval_slot_id = original_slot_id
        request.retrieval_round_id = original_round_id


def _evaluate(
    request: Any,
    decision: Any,
    bundle: EvidenceBundle,
    evaluate: EvaluateFn,
    *,
    attempted_retry: bool,
) -> Any:
    return evaluate(
        decision.legacy_route,
        bundle.metadata,
        attempted_retry=attempted_retry,
        prompt=request_planning_question(request),
        verification_domain=getattr(request, "verification_domain", None),
        origin=getattr(request, "origin", None),
    )


def _with_retrieval_rounds(
    bundle: EvidenceBundle,
    rounds: int,
) -> EvidenceBundle:
    metadata = dict(bundle.metadata)
    metadata["retrieval_rounds"] = rounds
    return EvidenceBundle(route=bundle.route, items=bundle.items, metadata=metadata)


def _merge_retrieval_metadata(
    first: dict[str, Any],
    second: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(first)
    for key, value in second.items():
        current = merged.get(key)
        if isinstance(current, list) and isinstance(value, list):
            merged[key] = _stable_union(current, value)
        elif isinstance(current, dict) and isinstance(value, dict):
            merged[key] = {**current, **value}
        elif value not in (None, "", [], {}):
            merged[key] = value
    return merged


def _stable_union(first: list[Any], second: list[Any]) -> list[Any]:
    output: list[Any] = []
    identities: set[str] = set()
    for item in [*first, *second]:
        identity = _retrieval_value_identity(item)
        if identity in identities:
            existing_index = next(
                index
                for index, existing in enumerate(output)
                if _retrieval_value_identity(existing) == identity
            )
            output[existing_index] = _merge_retrieval_value(
                output[existing_index],
                item,
            )
            continue
        identities.add(identity)
        output.append(item)
    return output


def _retrieval_value_identity(value: Any) -> str:
    if not isinstance(value, dict):
        return repr(value)
    try:
        return identity_of(value).key
    except ValueError:
        return repr(sorted(value.items()))


def _with_retrieval_lineage(
    metadata: dict[str, Any],
    *,
    round_id: int,
    query_id: str,
    slot_id: str,
) -> dict[str, Any]:
    output = dict(metadata or {})
    retriever_names = {
        "evidence": "text",
        "page_image_index": "visual",
        "element_index": "element",
        "elements": "element",
        "graph_evidence": "graph",
    }
    for key, retriever_name in retriever_names.items():
        value = output.get(key)
        if not isinstance(value, list):
            continue
        annotated = []
        for raw_rank, item in enumerate(value, start=1):
            if not isinstance(item, dict):
                annotated.append(item)
                continue
            record = dict(item)
            raw_score, score_type = _raw_retrieval_score(record, retriever_name)
            lineage = {
                "round_id": round_id,
                "query_id": query_id,
                "slot_id": slot_id,
                "retriever_name": retriever_name,
                "raw_rank": raw_rank,
                "raw_score": raw_score,
                "score_type": score_type,
            }
            record["retrieval_lineage"] = [
                *list(record.get("retrieval_lineage") or []),
                lineage,
            ]
            annotated.append(record)
        output[key] = annotated
    return output


def _raw_retrieval_score(
    item: dict[str, Any],
    retriever_name: str,
) -> tuple[float | None, str]:
    metadata = dict(item.get("metadata") or {})
    fields = {
        "text": ("retriever_score", "score"),
        "visual": ("visual_retriever_score", "score"),
        "element": ("element_retriever_score", "score"),
        "graph": ("graph_retriever_score", "score"),
    }
    for field in fields[retriever_name]:
        value = item.get(field, metadata.get(field))
        if value in (None, ""):
            continue
        return float(value), field
    return None, "not_recorded"


def _merge_retrieval_value(left: Any, right: Any) -> Any:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return left
    merged = dict(left)
    merged["retrieval_lineage"] = _stable_dict_union(
        list(left.get("retrieval_lineage") or []),
        list(right.get("retrieval_lineage") or []),
    )
    merged["source_backrefs"] = list(
        dict.fromkeys(
            [
                *list(left.get("source_backrefs") or []),
                *list(right.get("source_backrefs") or []),
            ]
        )
    )
    metadata = dict(left.get("metadata") or {})
    for key, value in dict(right.get("metadata") or {}).items():
        if key not in metadata:
            metadata[key] = value
    if metadata:
        merged["metadata"] = metadata
    return merged


def _stable_dict_union(
    first: list[dict[str, Any]],
    second: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for item in [*first, *second]:
        key = tuple(sorted((str(name), str(value)) for name, value in item.items()))
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output
