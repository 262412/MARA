from __future__ import annotations

from typing import Any

from ktem.docqa.controller import ROUTE_EVIDENCE_TYPES
from ktem.reasoning.mara_route_costing import (
    cost_gate_decision as route_cost_gate_decision,
)
from ktem.reasoning.mara_route_costing import (
    effective_route_confidences,
    latency_budget_reason,
    route_confidence_trace_fields,
    select_route_preserving_required_evidence,
    selection_reason,
)

from .mara_route_features import (
    _allowed_routes,
    _expected_route_cost,
    _expected_route_quality,
    _explicit_graph_request,
    _is_qasper_dataset,
    _normalized_route_probe,
    _question_features,
    _route_confidences,
    _route_scores,
    _skipped_expensive_routes,
)
from .mara_route_features import route_probe_from_metadata as _route_probe_from_metadata

route_probe_from_metadata = _route_probe_from_metadata


def score_adaptive_route(
    understanding: dict[str, Any],
    *,
    question: str,
    allowed_routes: Any = None,
    route_probe: dict[str, Any] | None = None,
    planner_route: str = "",
    planner_reason: str = "",
    dataset_family: str = "",
    latency_budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    allowed = _allowed_routes(allowed_routes)
    features = _question_features(understanding, question)
    probe = _normalized_route_probe(route_probe or {}, features)
    raw_confidences = _route_confidences(probe, features)
    confidences = effective_route_confidences(
        raw_confidences,
        features,
        dataset_family=dataset_family,
        latency_budget=latency_budget or {},
    )
    expected_quality = _expected_route_quality(
        features,
        confidences,
        probe,
        dataset_family,
    )
    expected_cost = _expected_route_cost(
        features,
        confidences,
        probe,
        dataset_family,
        latency_budget or {},
    )
    skipped_expensive_routes = _skipped_expensive_routes(
        features,
        confidences,
        probe,
        dataset_family,
        expected_quality,
        expected_cost,
    )
    if (
        _is_qasper_dataset(dataset_family)
        and not features["graph_intent"]
        and not _explicit_graph_request(planner_route, planner_reason)
        and "graph_global" not in skipped_expensive_routes
    ):
        skipped_expensive_routes.append("graph_global")
    route_scores, selected_route, preserve_required_evidence = _select_initial_route(
        expected_quality,
        expected_cost,
        features=features,
        planner_route=planner_route,
        planner_reason=planner_reason,
        allowed_routes=allowed,
        skipped_routes=skipped_expensive_routes,
    )
    return _adaptive_route_payload(
        selected_route=selected_route,
        preserve_required_evidence=preserve_required_evidence,
        planner_route=planner_route,
        planner_reason=planner_reason,
        features=features,
        probe=probe,
        raw_confidences=raw_confidences,
        confidences=confidences,
        expected_quality=expected_quality,
        expected_cost=expected_cost,
        skipped_expensive_routes=skipped_expensive_routes,
        allowed=allowed,
        route_scores=route_scores,
        latency_budget=latency_budget or {},
    )


def _select_initial_route(
    expected_quality: dict[str, float],
    expected_cost: dict[str, float],
    *,
    features: dict[str, Any],
    planner_route: str,
    planner_reason: str,
    allowed_routes: list[str],
    skipped_routes: list[str],
) -> tuple[dict[str, float], str, bool]:
    route_scores = _route_scores(expected_quality, expected_cost)
    if _explicit_graph_request(planner_route, planner_reason) and (
        not allowed_routes or "graph_global" in allowed_routes
    ):
        return route_scores, "graph_global", False
    (
        selected_route,
        preserve_required_evidence,
    ) = select_route_preserving_required_evidence(
        features=features,
        planner_route=planner_route,
        allowed_routes=allowed_routes,
        skipped_routes=skipped_routes,
        expected_quality=expected_quality,
        route_scores=route_scores,
    )
    return route_scores, selected_route, preserve_required_evidence


def _adaptive_route_payload(
    *,
    selected_route: str,
    preserve_required_evidence: bool,
    planner_route: str,
    planner_reason: str,
    features: dict[str, Any],
    probe: dict[str, Any],
    raw_confidences: dict[str, float],
    confidences: dict[str, float],
    expected_quality: dict[str, float],
    expected_cost: dict[str, float],
    skipped_expensive_routes: list[str],
    allowed: list[str],
    route_scores: dict[str, float],
    latency_budget: dict[str, Any],
) -> dict[str, Any]:
    latency_reason = latency_budget_reason(selected_route, features, confidences)
    reason = selection_reason(
        selected_route,
        planner_route=planner_route,
        planner_reason=planner_reason,
        latency_reason=latency_reason,
    )
    required_hybrid = features["structured_calculation"] and planner_route == "hybrid"
    required_evidence_route_available = (
        preserve_required_evidence if required_hybrid else None
    )
    if preserve_required_evidence:
        cost_gate_decision = "required_evidence_preserved"
    elif required_hybrid:
        cost_gate_decision = "required_hybrid_unavailable"
    else:
        cost_gate_decision = route_cost_gate_decision(selected_route, planner_route)
    return {
        "route": selected_route,
        "reason": reason,
        "evidence_types": list(ROUTE_EVIDENCE_TYPES.get(selected_route, ["text"])),
        "verify": selected_route not in {"direct", "abstain"},
        "routing_features": features,
        "route_scores": route_scores,
        "expected_route_quality": expected_quality,
        "expected_route_cost": expected_cost,
        **route_confidence_trace_fields(
            raw_confidences,
            confidences,
            skipped_expensive_routes,
            allowed,
            selected_route,
        ),
        "latency_budget": dict(latency_budget),
        "latency_budget_reason": latency_reason,
        "cost_gate_decision": cost_gate_decision,
        "required_evidence_route_available": required_evidence_route_available,
        "selected_route_reason": reason,
        "route_selection_reason": reason,
        "route_selection_policy": "cost_aware_initial",
        "planner_route": planner_route or selected_route,
        "scored_route": selected_route,
        "initial_route_decision": selected_route,
        "final_route": selected_route,
        "route_probe": probe,
    }
