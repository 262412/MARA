from __future__ import annotations

from typing import Any, Callable

from .evidence import EvidenceBundle, build_evidence_bundle
from .execution_verifier_rebind import verification_recovery_base_metadata
from .finance_calculation_recovery import calculation_recovery_requests
from .finance_typed_adequacy import ensure_finance_numeric_trace
from .query_planning import ensure_request_query_plan, request_planning_question
from .retrieval_metadata_merge import (
    merge_retrieval_metadata as _merge_retrieval_metadata,
)
from .route_budget import (
    optional_stage_allowed,
    route_budget_metadata,
    run_blocking_route_stage,
)
from .typed_retrieval_recovery import initial_query_metadata
from .typed_retrieval_recovery import (
    qasper_typed_recovery_required as _qasper_typed_recovery_required,
)
from .typed_retrieval_recovery import quality_retry_request as _quality_retry_request
from .typed_retrieval_recovery import recovery_query_metadata
from .typed_retrieval_recovery import (
    typed_qasper_recovery_requests as _typed_qasper_recovery_requests,
)
from .typed_retrieval_recovery import (
    typed_retrieval_recovery_has_progress as _typed_retrieval_recovery_has_progress,
)
from .typed_retrieval_recovery import (
    typed_retrieval_recovery_trace as _typed_retrieval_recovery_trace,
)
from .typed_retrieval_recovery import verification_slot_id as _verification_slot_id
from .typed_retrieval_recovery import verifier_recovery_query

EvaluateFn = Callable[..., Any]
RetrieveFn = Callable[[Any, Any], dict[str, Any]]
_MISSING = object()


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
    evidence_metadata = _retrieve_first_round(
        request,
        decision,
        retrieve,
        plan,
    )
    evidence_bundle = build_evidence_bundle(
        decision.legacy_route,
        request,
        evidence_metadata,
    )
    request.route_last_evidence_bundle = evidence_bundle
    retrieve_decision = _evaluate(
        request,
        decision,
        evidence_bundle,
        evaluate,
        attempted_retry=False,
    )
    initial_bundle = evidence_bundle
    second_round_requests = _second_round_requests(evidence_bundle)
    calculation_recovery = calculation_recovery_requests(second_round_requests)
    retry_for_slots = bool(second_round_requests)
    retry_for_quality = (
        retrieve_decision.status == "ambiguous" and retrieve_decision.retry
    ) or (retrieve_decision.status == "poor" and retrieve_decision.retry and retry_poor)
    if retry_for_quality and not second_round_requests:
        second_round_requests = [_quality_retry_request(request)]
    second_round_requests = _typed_qasper_recovery_requests(
        request,
        second_round_requests,
    )
    if min(max_rounds, plan.max_retrieval_rounds) < 2 or (
        not retry_for_slots and not retry_for_quality
    ):
        evidence_bundle = _with_retrieval_rounds(evidence_bundle, 1)
        request.route_last_evidence_bundle = evidence_bundle
        return evidence_bundle, retrieve_decision
    if not optional_stage_allowed(request):
        metadata = dict(evidence_bundle.metadata)
        metadata.update(route_budget_metadata(request))
        metadata["second_round_skipped_reason"] = "insufficient_remaining_time"
        evidence_bundle = EvidenceBundle(
            route=evidence_bundle.route,
            items=evidence_bundle.items,
            metadata=metadata,
        )
        evidence_bundle = _with_retrieval_rounds(evidence_bundle, 1)
        request.route_last_evidence_bundle = evidence_bundle
        return evidence_bundle, retrieve_decision

    return _complete_second_round(
        request,
        decision,
        retrieve,
        evaluate,
        evidence_metadata,
        initial_bundle,
        second_round_requests,
        calculation_recovery,
    )


def _complete_second_round(
    request: Any,
    decision: Any,
    retrieve: RetrieveFn,
    evaluate: EvaluateFn,
    evidence_metadata: dict[str, Any],
    initial_bundle: EvidenceBundle,
    second_round_requests: list[dict[str, Any]],
    calculation_recovery: list[dict[str, Any]],
) -> tuple[EvidenceBundle, Any]:
    second_round_metadata = _retrieve_second_round(
        request,
        decision,
        retrieve,
        second_round_requests,
    )
    merge_base = _second_round_merge_base(
        evidence_metadata,
        initial_bundle,
        calculation_recovery,
    )
    merged_metadata = _merge_retrieval_metadata(
        merge_base,
        second_round_metadata,
    )
    recovered_bundle = build_evidence_bundle(
        decision.legacy_route,
        request,
        merged_metadata,
    )
    recovered_bundle = _with_retrieval_rounds(recovered_bundle, 2)
    typed_recovery_no_progress = _qasper_typed_recovery_required(
        request
    ) and not _typed_retrieval_recovery_has_progress(initial_bundle, recovered_bundle)
    request.route_last_evidence_bundle = recovered_bundle
    retrieve_decision = _evaluate(
        request,
        decision,
        recovered_bundle,
        evaluate,
        attempted_retry=True,
    )
    if typed_recovery_no_progress:
        recovered_bundle.metadata["retrieval_stop_reason"] = "recovery_no_progress"
    if _qasper_typed_recovery_required(request):
        recovered_bundle.metadata["typed_retrieval_recovery_trace"] = (
            _typed_retrieval_recovery_trace(
                request,
                initial_bundle,
                recovered_bundle,
                second_round_requests,
                retrieve_decision,
            )
        )
    return recovered_bundle, retrieve_decision


def retrieve_for_verifier_recovery(
    request: Any,
    decision: Any,
    retrieve: RetrieveFn,
    bundle: EvidenceBundle,
    *,
    evaluate: EvaluateFn,
    retry_reason: str,
) -> tuple[EvidenceBundle, Any, str] | None:
    """Run the single focused retrieval round reserved for verifier recovery."""

    plan = ensure_request_query_plan(request)
    completed_rounds = int(bundle.metadata.get("retrieval_rounds") or 1)
    if int(bundle.metadata.get("verifier_focused_retrieval_attempt") or 0) >= 1:
        return None
    if not optional_stage_allowed(request):
        bundle.metadata.update(route_budget_metadata(request))
        bundle.metadata["verifier_recovery_skipped_reason"] = (
            "insufficient_remaining_time"
        )
        return None

    query = verifier_recovery_query(request)
    recovery_round = completed_rounds + 1
    recovery_metadata = _retrieve_second_round(
        request,
        decision,
        retrieve,
        [
            {
                "query_id": "verifier_recovery:1",
                "slot_id": _verification_slot_id(plan),
                "query": query,
                "modality": "text",
                "query_metadata": recovery_query_metadata(request),
            }
        ],
        round_id=recovery_round,
    )
    merged_metadata = _merge_retrieval_metadata(
        verification_recovery_base_metadata(bundle.metadata),
        recovery_metadata,
    )
    merged_metadata.update(
        {
            "verifier_recovery_attempt": 1,
            "verifier_focused_retrieval_attempt": 1,
            "verifier_recovery_round": recovery_round,
            "verifier_recovery_query": query,
            "verifier_recovery_retry_reason": retry_reason,
        }
    )
    recovered_bundle = build_evidence_bundle(
        decision.legacy_route,
        request,
        merged_metadata,
    )
    recovered_bundle = _with_retrieval_rounds(recovered_bundle, completed_rounds + 1)
    request.route_last_evidence_bundle = recovered_bundle
    recovered_decision = _evaluate(
        request,
        decision,
        recovered_bundle,
        evaluate,
        attempted_retry=True,
    )
    return recovered_bundle, recovered_decision, query


def _retrieve_first_round(
    request: Any,
    decision: Any,
    retrieve: RetrieveFn,
    plan: Any,
) -> dict[str, Any]:
    question = request_planning_question(request)
    requests = [
        {
            "query_id": f"round1:{slot.slot_id}",
            "slot_id": slot.slot_id,
            "query": slot.query,
            "query_metadata": initial_query_metadata(),
        }
        for slot in plan.evidence_slots
        if slot.required_for_retrieval and slot.query
    ]
    if not requests:
        query = str(getattr(request, "retrieval_query", "") or "").strip()
        requests = [
            {
                "query_id": "round1:primary",
                "slot_id": "",
                "query": query or question,
                "query_metadata": initial_query_metadata(),
            }
        ]
    original_query = str(getattr(request, "retrieval_query", "") or "")
    original_slot_id = str(getattr(request, "retrieval_slot_id", "") or "")
    original_round_id = int(getattr(request, "retrieval_round_id", 0) or 0)
    original_query_metadata = getattr(request, "retrieval_query_metadata", _MISSING)
    merged: dict[str, Any] = {}
    try:
        for retrieval_request in requests:
            request.retrieval_query = str(retrieval_request["query"])
            request.retrieval_slot_id = str(retrieval_request["slot_id"])
            request.retrieval_round_id = 1
            request.retrieval_query_metadata = dict(
                retrieval_request.get("query_metadata") or {}
            )
            response = _with_retrieval_query_contract(
                _with_retrieval_lineage(
                    run_blocking_route_stage(
                        request,
                        "retrieval",
                        retrieve,
                        request,
                        decision,
                        configured_timeout_seconds=getattr(
                            request, "retrieval_timeout_seconds", None
                        ),
                    ),
                    round_id=1,
                    query_id=str(retrieval_request["query_id"]),
                    slot_id=request.retrieval_slot_id,
                ),
                retrieval_request,
                round_id=1,
            )
            merged = _merge_retrieval_metadata(merged, response)
        return merged
    finally:
        request.retrieval_query = original_query
        request.retrieval_slot_id = original_slot_id
        request.retrieval_round_id = original_round_id
        _restore_query_metadata(request, original_query_metadata)


def _second_round_requests(bundle: EvidenceBundle) -> list[dict[str, Any]]:
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


def _second_round_merge_base(
    evidence_metadata: dict[str, Any],
    bundle: EvidenceBundle,
    calculation_recovery: list[dict[str, Any]],
) -> dict[str, Any]:
    base = dict(evidence_metadata)
    if not calculation_recovery:
        return base
    trace = dict(bundle.metadata.get("calculation_recovery_trace") or {})
    trace.update(
        {
            "attempt_count": int(trace.get("attempt_count") or 0) + 1,
            "status": "retrieving",
            "targeted_requests": [dict(item) for item in calculation_recovery],
        }
    )
    base["calculation_recovery_trace"] = trace
    return base


def _retrieve_second_round(
    request: Any,
    decision: Any,
    retrieve: RetrieveFn,
    requests: list[dict[str, Any]],
    *,
    round_id: int = 2,
) -> dict[str, Any]:
    original_query = str(getattr(request, "retrieval_query", "") or "")
    original_slot_id = str(getattr(request, "retrieval_slot_id", "") or "")
    original_round_id = int(getattr(request, "retrieval_round_id", 0) or 0)
    original_query_metadata = getattr(request, "retrieval_query_metadata", _MISSING)
    merged: dict[str, Any] = {}
    try:
        for retrieval_request in requests:
            request.retrieval_query = str(retrieval_request.get("query") or "")
            request.retrieval_slot_id = str(retrieval_request.get("slot_id") or "")
            request.retrieval_round_id = round_id
            query_metadata = dict(
                retrieval_request.get("query_metadata")
                or {
                    "contract_id": "recovery_query.v1",
                    "query_kind": "recovery",
                }
            )
            request.retrieval_query_metadata = query_metadata
            traced_request = {**retrieval_request, "query_metadata": query_metadata}
            response = _with_retrieval_query_contract(
                _with_retrieval_lineage(
                    run_blocking_route_stage(
                        request,
                        "retrieval_recovery",
                        retrieve,
                        request,
                        decision,
                        configured_timeout_seconds=getattr(
                            request, "retrieval_timeout_seconds", None
                        ),
                    ),
                    round_id=round_id,
                    query_id=str(retrieval_request.get("query_id") or ""),
                    slot_id=request.retrieval_slot_id,
                ),
                traced_request,
                round_id=round_id,
            )
            merged = _merge_retrieval_metadata(merged, response)
        return merged
    finally:
        request.retrieval_query = original_query
        request.retrieval_slot_id = original_slot_id
        request.retrieval_round_id = original_round_id
        _restore_query_metadata(request, original_query_metadata)


def _restore_query_metadata(request: Any, original: Any) -> None:
    if original is _MISSING:
        if hasattr(request, "retrieval_query_metadata"):
            delattr(request, "retrieval_query_metadata")
        return
    request.retrieval_query_metadata = original


def _evaluate(
    request: Any,
    decision: Any,
    bundle: EvidenceBundle,
    evaluate: EvaluateFn,
    *,
    attempted_retry: bool,
) -> Any:
    ensure_finance_numeric_trace(request, bundle)
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


def _with_retrieval_query_contract(
    metadata: dict[str, Any],
    retrieval_request: dict[str, Any],
    *,
    round_id: int,
) -> dict[str, Any]:
    output = dict(metadata or {})
    query_metadata = dict(retrieval_request.get("query_metadata") or {})
    output["retrieval_query_contracts"] = [
        {
            **query_metadata,
            "round_id": round_id,
            "query_id": str(retrieval_request.get("query_id") or ""),
            "slot_id": str(retrieval_request.get("slot_id") or ""),
            "query": str(retrieval_request.get("query") or ""),
        }
    ]
    return output


def _with_retrieval_lineage(
    metadata: dict[str, Any],
    *,
    round_id: int,
    query_id: str,
    slot_id: str,
) -> dict[str, Any]:
    output = dict(metadata or {})
    _record_reranker_query_context(
        output,
        round_id=round_id,
        query_id=query_id,
        slot_id=slot_id,
    )
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
            record_metadata = record.get("metadata")
            record_metadata = (
                record_metadata if isinstance(record_metadata, dict) else {}
            )
            existing_lineage = [
                dict(entry)
                for entry in (
                    record.get("retrieval_lineage")
                    or record_metadata.get("retrieval_lineage")
                    or []
                )
                if isinstance(entry, dict)
            ]
            if existing_lineage:
                record["retrieval_lineage"] = existing_lineage
                annotated.append(record)
                continue
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
                lineage,
            ]
            annotated.append(record)
        output[key] = annotated
    return output


def _record_reranker_query_context(
    metadata: dict[str, Any],
    *,
    round_id: int,
    query_id: str,
    slot_id: str,
) -> None:
    traces = [
        dict(trace)
        for trace in metadata.get("reranker_execution_traces") or []
        if isinstance(trace, dict)
    ]
    legacy_trace = metadata.get("reranker_execution_trace")
    if isinstance(legacy_trace, dict) and not traces:
        traces.append(dict(legacy_trace))
    if not traces:
        return
    contextualized = []
    for trace in traces:
        trace.update(
            {
                "round_id": round_id,
                "query_id": query_id,
                "slot_id": slot_id,
            }
        )
        contextualized.append(trace)
    metadata["reranker_execution_traces"] = contextualized
    metadata["reranker_execution_trace"] = contextualized[-1]


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
