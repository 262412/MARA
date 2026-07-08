from __future__ import annotations

import json
from typing import Any

from ktem.docqa.controller import ROUTE_EVIDENCE_TYPES, parse_planner_decision
from ktem.reasoning.mara_route_scorer import score_adaptive_route

_STRUCTURED_CALCULATION_TERMS = (
    "average",
    "calculate",
    "calculation",
    "change",
    "count",
    "difference",
    "margin",
    "percentage",
    "rate",
    "ratio",
    "sum",
    "total",
)
_STRUCTURED_CALCULATION_CONTEXT_TERMS = (
    "based on",
    "from the table",
    "in the table",
    "using the",
)
_VISUAL_INTENT_TERMS = {
    "chart",
    "diagram",
    "figure",
    "graph",
    "image",
    "layout",
    "plot",
    "shown",
    "slide",
    "visual",
    "visible",
}
_VISUAL_MODALITIES = {"figure", "slide", "table", "formula", "page_image"}


class LLMPlanner:
    def __init__(self, planner_model: str) -> None:
        self.planner_model = planner_model

    def __call__(self, payload: dict[str, Any]) -> str:
        return _run_planner_model(payload, self.planner_model)


def planner_decision(
    understanding: dict[str, Any],
    *,
    planner: Any = None,
    planner_model: str | None = None,
    question: str = "",
    allowed_routes: Any = None,
    route_probe: dict[str, Any] | None = None,
    dataset_family: str = "",
    latency_budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if planner is not None:
        return _call_structured_planner(
            planner,
            understanding,
            planner_model=planner_model,
            question=question,
            allowed_routes=allowed_routes,
            route_probe=route_probe,
            dataset_family=dataset_family,
            latency_budget=latency_budget,
        )
    if planner_model:
        return _call_structured_planner(
            LLMPlanner(planner_model),
            understanding,
            planner_model=planner_model,
            question=question,
            allowed_routes=allowed_routes,
            route_probe=route_probe,
            dataset_family=dataset_family,
            latency_budget=latency_budget,
        )
    decision = _constrain_heuristic_decision(
        _heuristic_planner_decision(
            understanding,
            question=question,
            allowed_routes=allowed_routes,
        ),
        allowed_routes=allowed_routes,
    )
    if not route_probe:
        return decision
    return score_adaptive_route(
        understanding,
        question=question,
        allowed_routes=allowed_routes,
        route_probe=route_probe,
        planner_route=str(decision.get("route") or ""),
        planner_reason=str(decision.get("reason") or ""),
        dataset_family=dataset_family,
        latency_budget=latency_budget,
    )


def planner_trace_payload(
    understanding: dict[str, Any],
    *,
    planner: Any = None,
    planner_model: str | None = None,
    question: str = "",
    allowed_routes: Any = None,
    route_probe: dict[str, Any] | None = None,
    dataset_family: str = "",
    latency_budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "event": "planner_output",
        "decision": planner_decision(
            understanding,
            planner=planner,
            planner_model=planner_model,
            question=question,
            allowed_routes=allowed_routes,
            route_probe=route_probe,
            dataset_family=dataset_family,
            latency_budget=latency_budget,
        ),
    }
    if planner_model:
        payload["planner_model"] = planner_model
    return payload


def _heuristic_planner_decision(
    understanding: dict[str, Any],
    *,
    question: str = "",
    allowed_routes: Any = None,
) -> dict[str, Any]:
    task_type = str(understanding.get("task_type") or "qa")
    modalities = [
        str(modality)
        for modality in understanding.get("modalities", ["text"])
        if modality
    ]
    available_modalities = [
        str(modality)
        for modality in understanding.get("available_modalities", [])
        if modality
    ]
    scope = str(understanding.get("scope") or "document")
    question_text = " ".join(
        str(value or "")
        for value in (
            question,
            understanding.get("question"),
            understanding.get("query"),
        )
    ).lower()

    if task_type == "summary" and _has_selected_source_context(understanding):
        return _source_summary_decision()
    if task_type in {"compare", "study_guide", "summary"} and scope != "page":
        return {
            "route": "graph_global",
            "reason": "Global compare and study tasks use graph evidence.",
            "evidence_types": ["graph"],
            "verify": True,
        }
    if _is_structured_calculation_question(question_text):
        return _route_payload(
            "hybrid",
            (
                "Structured calculation questions use hybrid evidence so text, "
                "page-image, and element routes can recover source values."
            ),
            ["text", "page_image", "element"],
            question_text=question_text,
            modalities=modalities,
            available_modalities=available_modalities,
            scope=scope,
            latency_budget_reason="hybrid_allowed_for_structured_calculation",
            calculation_scope="structured_document_calculation",
        )
    if any(modality in _VISUAL_MODALITIES for modality in modalities):
        return _visual_modality_decision(
            question_text,
            modalities=modalities,
            available_modalities=available_modalities,
            scope=scope,
            allowed_routes=allowed_routes,
        )
    if "page_image" in available_modalities:
        decision = _page_image_available_decision(
            question_text,
            modalities=modalities,
            available_modalities=available_modalities,
            scope=scope,
            allowed_routes=allowed_routes,
        )
        if decision is not None:
            return decision
    return _route_payload(
        "doc",
        "Document text evidence is the default retrieval route.",
        ["text"],
        question_text=question_text,
        modalities=modalities,
        available_modalities=available_modalities,
        scope=scope,
        latency_budget_reason="text_default",
    )


def _is_structured_calculation_question(question_text: str) -> bool:
    has_calculation_term = any(
        term in question_text for term in _STRUCTURED_CALCULATION_TERMS
    )
    if not has_calculation_term:
        return False
    return any(term in question_text for term in _STRUCTURED_CALCULATION_CONTEXT_TERMS)


def _visual_modality_decision(
    question_text: str,
    *,
    modalities: list[str],
    available_modalities: list[str],
    scope: str,
    allowed_routes: Any,
) -> dict[str, Any]:
    route = (
        "doc_page_image"
        if _route_is_allowed("doc_page_image", allowed_routes)
        else "hybrid"
    )
    evidence_types = (
        ["page_image"]
        if route == "doc_page_image"
        else ["text", "page_image", "element"]
    )
    return _route_payload(
        route,
        "Visual document questions use page-image evidence before broad hybrid fusion.",
        evidence_types,
        question_text=question_text,
        modalities=modalities,
        available_modalities=available_modalities,
        scope=scope,
        latency_budget_reason="visual_intent_justifies_visual_route",
    )


def _page_image_available_decision(
    question_text: str,
    *,
    modalities: list[str],
    available_modalities: list[str],
    scope: str,
    allowed_routes: Any,
) -> dict[str, Any] | None:
    if _has_visual_intent(question_text) and _route_is_allowed(
        "doc_page_image", allowed_routes
    ):
        return _route_payload(
            "doc_page_image",
            "Question has visual intent and page-image evidence is available.",
            ["page_image"],
            question_text=question_text,
            modalities=modalities,
            available_modalities=available_modalities,
            scope=scope,
            latency_budget_reason="visual_intent_justifies_visual_route",
        )
    if _route_is_allowed("doc_text", allowed_routes):
        return _route_payload(
            "doc_text",
            (
                "Page-image evidence is available, but the question is text-"
                "answerable enough to avoid visual generation cost."
            ),
            ["text"],
            question_text=question_text,
            modalities=modalities,
            available_modalities=available_modalities,
            scope=scope,
            latency_budget_reason="text_route_avoids_visual_latency",
        )
    if _route_is_allowed("doc_page_image", allowed_routes):
        return _route_payload(
            "doc_page_image",
            "Page-image evidence is available for this question.",
            ["page_image"],
            question_text=question_text,
            modalities=modalities,
            available_modalities=available_modalities,
            scope=scope,
            latency_budget_reason="text_route_unavailable",
        )
    return None


def _has_visual_intent(question_text: str) -> bool:
    tokens = set(question_text.split())
    return bool(tokens & _VISUAL_INTENT_TERMS) or any(
        term in question_text for term in _VISUAL_INTENT_TERMS
    )


def _route_payload(
    route: str,
    reason: str,
    evidence_types: list[str],
    *,
    question_text: str,
    modalities: list[str],
    available_modalities: list[str],
    scope: str,
    latency_budget_reason: str,
    **extra: Any,
) -> dict[str, Any]:
    features = _routing_features(
        question_text,
        modalities=modalities,
        available_modalities=available_modalities,
        scope=scope,
    )
    payload = {
        "route": route,
        "reason": reason,
        "evidence_types": evidence_types,
        "verify": route not in {"direct", "abstain"},
        "routing_features": features,
        "route_scores": _route_scores(features),
        "latency_budget_reason": latency_budget_reason,
        "selected_route_reason": reason,
    }
    payload.update(extra)
    return payload


def _routing_features(
    question_text: str,
    *,
    modalities: list[str],
    available_modalities: list[str],
    scope: str,
) -> dict[str, Any]:
    return {
        "visual_intent": _has_visual_intent(question_text)
        or any(modality in _VISUAL_MODALITIES for modality in modalities),
        "structured_calculation": _is_structured_calculation_question(question_text),
        "page_image_available": "page_image" in available_modalities,
        "scope": scope,
    }


def _route_scores(features: dict[str, Any]) -> dict[str, float]:
    visual_intent = bool(features.get("visual_intent"))
    structured = bool(features.get("structured_calculation"))
    page_image_available = bool(features.get("page_image_available"))
    scores = {
        "doc_text": 0.65,
        "doc_page_image": 0.15,
        "hybrid": 0.25,
        "doc_element": 0.2,
        "graph_global": 0.1,
    }
    if structured:
        scores["hybrid"] += 0.65
        scores["doc_text"] -= 0.1
    elif visual_intent and page_image_available:
        scores["doc_page_image"] += 0.7
        scores["hybrid"] += 0.15
    elif page_image_available:
        scores["doc_text"] += 0.25
        scores["hybrid"] -= 0.15
        scores["doc_page_image"] -= 0.05
    if not page_image_available:
        scores["doc_page_image"] = 0.0
    return {key: round(value, 4) for key, value in scores.items()}


def _has_selected_source_context(understanding: dict[str, Any]) -> bool:
    return bool(understanding.get("selected_source_context"))


def _source_summary_decision() -> dict[str, Any]:
    return {
        "route": "doc",
        "reason": "Selected source summaries use document text evidence.",
        "evidence_types": ["text"],
        "verify": True,
    }


def _constrain_heuristic_decision(
    decision: dict[str, Any],
    *,
    allowed_routes: Any,
) -> dict[str, Any]:
    if not allowed_routes:
        return decision
    unconstrained_decision = parse_planner_decision(decision)
    route_decision = parse_planner_decision(decision, allowed_routes=allowed_routes)
    if route_decision.route == unconstrained_decision.route:
        normalized = dict(decision)
        normalized["route"] = route_decision.route
        return normalized
    return {
        "route": route_decision.route,
        "reason": (
            f"{decision.get('reason') or route_decision.reason} "
            f"Constrained to {route_decision.route} by allowed routes."
        ),
        "evidence_types": _evidence_types_for_route(route_decision.route),
        "verify": route_decision.route not in {"direct", "abstain"},
    }


def _route_is_allowed(route: str, allowed_routes: Any) -> bool:
    allowed = [str(item).strip() for item in allowed_routes or [] if str(item).strip()]
    return not allowed or route in allowed


def _call_structured_planner(
    planner: Any,
    understanding: dict[str, Any],
    *,
    planner_model: str | None,
    question: str,
    allowed_routes: Any,
    route_probe: dict[str, Any] | None,
    dataset_family: str,
    latency_budget: dict[str, Any] | None,
) -> dict[str, Any]:
    planner_payload: dict[str, Any] = {
        "question": question,
        "understanding": dict(understanding),
        "planner_model": planner_model or "",
        "allowed_routes": list(allowed_routes or []),
    }
    try:
        raw_decision = planner(planner_payload)
    except (ImportError, RuntimeError, ValueError) as exc:
        return {
            "route": "abstain",
            "reason": f"Planner model failed; backend unavailable: {exc}",
            "planner_error": str(exc),
            "evidence_types": [],
            "verify": False,
        }
    decision = parse_planner_decision(raw_decision, allowed_routes=allowed_routes)
    payload: dict[str, Any] = {
        "route": decision.route,
        "reason": decision.reason,
        "evidence_types": _evidence_types_for_route(decision.route),
        "verify": decision.route not in {"direct", "abstain"},
    }
    if decision.route in {"direct", "abstain"}:
        return payload
    return score_adaptive_route(
        understanding,
        question=question,
        allowed_routes=allowed_routes,
        route_probe=route_probe,
        planner_route=decision.route,
        planner_reason=decision.reason,
        dataset_family=dataset_family,
        latency_budget=latency_budget,
    )


def _normalize_cost_aware_planner_decision(
    decision: dict[str, Any],
    understanding: dict[str, Any],
    *,
    question: str,
    allowed_routes: Any,
) -> dict[str, Any]:
    route = str(decision.get("route") or "").strip()
    if route not in {"graph_global", "hybrid"}:
        return decision
    task_type = str(understanding.get("task_type") or "qa")
    if task_type != "qa":
        return decision
    modalities = [
        str(modality)
        for modality in understanding.get("modalities", ["text"])
        if modality
    ]
    available_modalities = [
        str(modality)
        for modality in understanding.get("available_modalities", [])
        if modality
    ]
    question_text = " ".join(
        str(value or "")
        for value in (
            question,
            understanding.get("question"),
            understanding.get("query"),
        )
    ).lower()
    scope = str(understanding.get("scope") or "document")
    features = _routing_features(
        question_text,
        modalities=modalities,
        available_modalities=available_modalities,
        scope=scope,
    )
    normalized_route = ""
    latency_reason = ""
    if features["visual_intent"] and _route_is_allowed(
        "doc_page_image", allowed_routes
    ):
        normalized_route = "doc_page_image"
        latency_reason = "visual_intent_justifies_visual_route"
    elif _route_is_allowed("doc_text", allowed_routes):
        normalized_route = "doc_text"
        latency_reason = "text_route_avoids_visual_latency"
    if not normalized_route or normalized_route == route:
        return decision
    reason = (
        f"{decision.get('reason') or 'Planner selected a broad route.'} "
        f"Cost-aware calibration selected {normalized_route} for QA execution."
    )
    return _route_payload(
        normalized_route,
        reason,
        _evidence_types_for_route(normalized_route),
        question_text=question_text,
        modalities=modalities,
        available_modalities=available_modalities,
        scope=scope,
        latency_budget_reason=latency_reason,
        cost_gate_decision=f"normalized_from_{route}",
        original_planner_route=route,
    )


def _evidence_types_for_route(route: str) -> list[str]:
    return list(ROUTE_EVIDENCE_TYPES.get(route, ["text"]))


def _run_planner_model(payload: dict[str, Any], planner_model: str) -> str:
    from kotaemon.modelcli import (
        ModelRequest,
        build_registry,
        load_runtime_config,
        run_completion,
    )

    prompt = json.dumps(payload, ensure_ascii=False, indent=2)
    request = ModelRequest(
        prompt=prompt,
        model=planner_model,
        system_prompt=(
            "Select one route for MARA DocQA. Return only JSON with route and "
            "reason. Allowed route aliases include direct, doc, visual, element, "
            "graph, hybrid, and abstain."
        ),
        temperature=0.0,
        max_tokens=300,
    )
    response = run_completion(
        build_registry(), load_runtime_config("modelcli.yml"), request
    )
    return response.text
