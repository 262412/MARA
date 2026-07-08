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
        and not features["visual_intent"]
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
