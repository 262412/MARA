from __future__ import annotations

from typing import Any, Callable

from .evidence import EvidenceBundle, build_evidence_bundle

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
    evidence_metadata = retrieve(request, decision)
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
    second_round_queries = list(
        evidence_bundle.metadata.get("second_round_queries") or []
    )
    retry_for_slots = bool(second_round_queries)
    retry_for_quality = (
        retrieve_decision.status == "ambiguous" and retrieve_decision.retry
    ) or (retrieve_decision.status == "poor" and retrieve_decision.retry and retry_poor)
    if max_rounds < 2 or (not retry_for_slots and not retry_for_quality):
        return _with_retrieval_rounds(evidence_bundle, 1), retrieve_decision

    second_round_metadata = _retrieve_second_round(
        request,
        decision,
        retrieve,
        second_round_queries,
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


def _retrieve_second_round(
    request: Any,
    decision: Any,
    retrieve: RetrieveFn,
    queries: list[str],
) -> dict[str, Any]:
    original_query = str(getattr(request, "retrieval_query", "") or "")
    if queries:
        request.retrieval_query = "\n".join(queries)
    try:
        return retrieve(request, decision)
    finally:
        request.retrieval_query = original_query


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
        prompt=str(getattr(request, "prompt", "") or ""),
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
            continue
        identities.add(identity)
        output.append(item)
    return output


def _retrieval_value_identity(value: Any) -> str:
    if not isinstance(value, dict):
        return repr(value)
    identifier = str(
        value.get("canonical_id")
        or value.get("evidence_id")
        or value.get("doc_id")
        or value.get("element_id")
        or ""
    ).strip()
    return identifier or repr(sorted(value.items()))
