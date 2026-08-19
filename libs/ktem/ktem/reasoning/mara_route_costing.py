from __future__ import annotations

from typing import Any


def effective_route_confidences(
    confidences: dict[str, float],
    features: dict[str, Any],
    *,
    dataset_family: str,
    latency_budget: dict[str, Any],
) -> dict[str, float]:
    effective = dict(confidences)
    dataset = dataset_text(dataset_family, latency_budget)
    if (
        is_mmdocrag_dataset(dataset)
        and not (
            features["visual_intent"]
            or features.get("requires_typed_visual_evidence", False)
        )
        and effective.get("text", 0.0) >= 0.65
    ):
        effective["visual"] = min(effective.get("visual", 0.0), 0.45)
    return {key: round(value, 4) for key, value in effective.items()}


def select_route(
    route_scores: dict[str, float],
    allowed_routes: list[str],
    skipped_routes: list[str] | None = None,
) -> str:
    allowed = allowed_routes or list(route_scores)
    skipped = set(skipped_routes or [])
    candidates = [
        (score, route)
        for route, score in route_scores.items()
        if route in allowed
        and route not in {"direct", "abstain"}
        and route not in skipped
    ]
    if not candidates:
        if "doc_text" in allowed:
            return "doc_text"
        return allowed[0] if allowed else "doc_text"
    return max(candidates, key=lambda item: (item[0], route_tie_breaker(item[1])))[1]


def select_route_preserving_required_evidence(
    *,
    features: dict[str, Any],
    planner_route: str,
    allowed_routes: list[str],
    skipped_routes: list[str],
    expected_quality: dict[str, float],
    route_scores: dict[str, float],
) -> tuple[str, bool]:
    preserve_typed_visual_evidence = (
        features.get("requires_typed_visual_evidence", False)
        and planner_route in {"doc_page_image", "hybrid"}
        and (not allowed_routes or planner_route in allowed_routes)
        and planner_route not in skipped_routes
        and expected_quality.get(planner_route, 0.0) > 0.0
    )
    typed_visual_route = (
        planner_route
        if preserve_typed_visual_evidence
        else (
            "doc_page_image"
            if features.get("requires_typed_visual_evidence", False)
            and (not allowed_routes or "doc_page_image" in allowed_routes)
            and "doc_page_image" not in skipped_routes
            and expected_quality.get("doc_page_image", 0.0) > 0.0
            else ""
        )
    )
    preserve_required_evidence = bool(typed_visual_route) or (
        features["structured_calculation"]
        and planner_route == "hybrid"
        and (not allowed_routes or "hybrid" in allowed_routes)
        and "hybrid" not in skipped_routes
        and expected_quality.get("hybrid", 0.0) > 0.0
    )
    route = (
        typed_visual_route
        if typed_visual_route
        else (
            "hybrid"
            if preserve_required_evidence
            else select_route(route_scores, allowed_routes, skipped_routes)
        )
    )
    return route, preserve_required_evidence


def cost_gate_enforced_routes(
    skipped_routes: list[str],
    allowed_routes: list[str],
    selected_route: str,
) -> list[str]:
    return [
        route
        for route in skipped_routes
        if route in allowed_routes and route != selected_route
    ]


def route_confidence_trace_fields(
    raw_confidences: dict[str, float],
    confidences: dict[str, float],
    skipped_routes: list[str],
    allowed_routes: list[str],
    selected_route: str,
) -> dict[str, Any]:
    return {
        "raw_route_confidence_by_modality": raw_confidences,
        "route_confidences": confidences,
        "route_confidence_by_modality": confidences,
        "skipped_expensive_routes": skipped_routes,
        "cost_gate_enforced_routes": cost_gate_enforced_routes(
            skipped_routes, allowed_routes, selected_route
        ),
    }


def route_tie_breaker(route: str) -> int:
    order = {
        "doc_text": 5,
        "doc_page_image": 4,
        "doc_element": 3,
        "hybrid": 2,
        "graph_global": 1,
    }
    return order.get(route, 0)


def dataset_text(dataset_family: str, latency_budget: dict[str, Any]) -> str:
    return " ".join(
        str(value or "").lower()
        for value in (dataset_family, latency_budget.get("dataset_family"))
    )


def is_mmdocrag_dataset(dataset: str) -> bool:
    return "mmdocrag" in dataset or "multimodal_doc_qa" in dataset


def latency_budget_reason(
    route: str,
    features: dict[str, Any],
    confidences: dict[str, float],
) -> str:
    if route == "doc_text":
        return "text_route_avoids_visual_latency"
    if route == "doc_page_image":
        return "visual_intent_justifies_visual_route"
    if route == "doc_element":
        return "element_confidence_justifies_element_route"
    if route == "graph_global":
        return "graph_context_justifies_global_route"
    if route == "hybrid":
        return "complementary_evidence_justifies_hybrid_route"
    if features["visual_intent"] and confidences["visual"] < 0.6:
        return "visual_confidence_below_vlm_gate"
    return "route_score_selected"


def selection_reason(
    route: str,
    *,
    planner_route: str,
    planner_reason: str,
    latency_reason: str,
) -> str:
    prefix = planner_reason.strip() or "Controller selected an initial route."
    if planner_route and planner_route != route:
        return (
            f"{prefix} Cost-aware scoring selected {route} before retrieval "
            f"execution ({latency_reason})."
        )
    return f"{prefix} Cost-aware scoring selected {route} ({latency_reason})."


def cost_gate_decision(route: str, planner_route: str) -> str:
    if planner_route and planner_route != route:
        return f"normalized_from_{planner_route}"
    if route == "doc_text":
        return "text_cost_gate_passed"
    if route == "doc_page_image":
        return "visual_cost_gate_passed"
    return f"{route}_cost_gate_passed"
