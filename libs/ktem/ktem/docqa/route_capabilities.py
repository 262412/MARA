from __future__ import annotations

from typing import Any

from ktem.reasoning.mara_visual_intent import has_explicit_visual_intent

from .query_planning import request_planning_question

_ROUTE_IDS = {
    "direct",
    "doc_text",
    "doc_page_image",
    "doc_element",
    "graph_global",
    "hybrid",
    "abstain",
}


def route_switch_candidates(request: Any, current_route: str) -> list[str]:
    candidates, _rejected = route_switch_candidate_evaluation(
        request,
        current_route,
    )
    return candidates


def route_switch_candidate_evaluation(
    request: Any,
    current_route: str,
) -> tuple[list[str], list[dict[str, str]]]:
    allowed_routes = list(getattr(request, "allowed_routes", []) or [])
    preferred_order = _cost_aware_route_switch_order(request)
    allowed = [route for route in preferred_order if route in allowed_routes]
    allowed.extend(route for route in allowed_routes if route not in allowed)
    eligible = [
        route
        for route in allowed
        if route in _ROUTE_IDS and route not in {current_route, "direct", "abstain"}
    ]
    rejected = [
        {
            "route": route,
            "reason": "backend_unavailable:visual_generator",
        }
        for route in eligible
        if _route_backend_unavailable(request, route)
    ]
    return (
        [route for route in eligible if not _route_backend_unavailable(request, route)],
        rejected,
    )


def _route_backend_unavailable(request: Any, route: str) -> bool:
    if route != "doc_page_image":
        return False
    if has_explicit_visual_intent(request_planning_question(request).lower()):
        return False
    return not bool(
        getattr(request, "vlm_generator", None)
        or str(getattr(request, "visual_generator_backend", "") or "").strip()
    )


def _cost_aware_route_switch_order(request: Any) -> list[str]:
    prompt = request_planning_question(request).lower()
    if has_explicit_visual_intent(prompt):
        return ["doc_page_image", "doc_text", "hybrid", "doc_element", "graph_global"]
    return ["doc_text", "doc_page_image", "hybrid", "doc_element", "graph_global"]
