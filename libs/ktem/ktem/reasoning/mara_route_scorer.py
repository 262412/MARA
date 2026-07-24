from __future__ import annotations

import re
from typing import Any

from ktem.docqa.controller import ROUTE_EVIDENCE_TYPES
from ktem.reasoning.mara_route_costing import (
    cost_gate_decision as route_cost_gate_decision,
)
from ktem.reasoning.mara_route_costing import (
    dataset_text,
    effective_route_confidences,
    is_mmdocrag_dataset,
    latency_budget_reason,
    route_confidence_trace_fields,
    select_route_preserving_required_evidence,
    selection_reason,
)
from ktem.reasoning.mara_visual_intent import has_explicit_visual_intent

VISUAL_MODALITIES = {"figure", "image", "page_image", "slide"}
ELEMENT_INTENT_TERMS = {
    "cell",
    "formula",
    "row",
    "table",
    "tabular",
}
ELEMENT_MODALITIES = {"formula", "table"}
CALCULATION_TERMS = {
    "amount",
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
    "value",
}
SUMMARY_TASK_TYPES = {"compare", "study_guide", "summary"}


def route_probe_from_metadata(
    modality: str,
    metadata: dict[str, Any],
    *,
    backend_healthy: bool = True,
) -> dict[str, Any]:
    records = _records_for_modality(modality, metadata)
    scores = _scores_for_modality(modality, metadata, records)
    top_score = scores[0] if scores else 0.0
    second_score = scores[1] if len(scores) > 1 else 0.0
    return {
        "evidence_count": len(records),
        "top_score": round(top_score, 4),
        "top_margin": round(max(top_score - second_score, 0.0), 4),
        "locator_quality": _locator_quality(records, metadata),
        "top_pages": _unique(item.get("page_label") for item in records[:3]),
        "top_sources": _unique(
            item.get("file_id") or item.get("source_id") for item in records[:3]
        ),
        "has_text_or_ocr": any(_has_text_or_ocr(item) for item in records[:3]),
        "backend_healthy": bool(backend_healthy),
    }


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
    route_scores = _route_scores(expected_quality, expected_cost)
    (
        selected_route,
        preserve_required_evidence,
    ) = select_route_preserving_required_evidence(
        features=features,
        planner_route=planner_route,
        allowed_routes=allowed,
        skipped_routes=skipped_expensive_routes,
        expected_quality=expected_quality,
        route_scores=route_scores,
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
    cost_gate_decision = (
        "required_evidence_preserved"
        if preserve_required_evidence
        else route_cost_gate_decision(selected_route, planner_route)
    )
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
        "selected_route_reason": reason,
        "route_selection_reason": reason,
        "route_selection_policy": "cost_aware_initial",
        "planner_route": planner_route or selected_route,
        "scored_route": selected_route,
        "initial_route_decision": selected_route,
        "final_route": selected_route,
        "route_probe": probe,
    }


def _records_for_modality(
    modality: str, metadata: dict[str, Any]
) -> list[dict[str, Any]]:
    if modality == "text":
        return [dict(item) for item in metadata.get("evidence") or []]
    if modality == "visual":
        return [dict(item) for item in metadata.get("page_image_index") or []]
    if modality == "element":
        return [dict(item) for item in metadata.get("element_index") or []]
    if modality == "graph":
        return [dict(item) for item in metadata.get("graph_evidence") or []]
    return []


def _scores_for_modality(
    modality: str,
    metadata: dict[str, Any],
    records: list[dict[str, Any]],
) -> list[float]:
    score_maps = {
        "visual": metadata.get("visual_retriever_scores") or {},
        "element": metadata.get("element_retriever_scores") or {},
    }
    mapped_scores = dict(score_maps.get(modality) or {})
    scores: list[float] = []
    for item in records:
        evidence_id = str(item.get("evidence_id") or "").strip()
        metadata_score = dict(item.get("metadata") or {}).get(f"{modality}_score")
        raw_score = (
            mapped_scores.get(evidence_id)
            if evidence_id in mapped_scores
            else item.get("score") or metadata_score
        )
        scores.append(_bounded_score(raw_score))
    return sorted(scores, reverse=True)


def _bounded_score(value: Any) -> float:
    try:
        score = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if score <= 0.0:
        return 0.0
    return min(score, 1.0)


def _locator_quality(records: list[dict[str, Any]], metadata: dict[str, Any]) -> float:
    if not records:
        return 0.0
    located = [
        item
        for item in records
        if str(item.get("page_label") or "").strip()
        and str(item.get("file_id") or item.get("source_id") or "").strip()
    ]
    if located:
        return round(len(located) / len(records), 4)
    if metadata.get("page_coverage") and metadata.get("source_ids"):
        return 0.7
    return 0.0


def _has_text_or_ocr(item: dict[str, Any]) -> bool:
    return bool(str(item.get("text") or item.get("ocr_text") or "").strip())


def _question_features(
    understanding: dict[str, Any],
    question: str,
) -> dict[str, Any]:
    task_type = str(understanding.get("task_type") or "qa").strip() or "qa"
    modalities = [
        str(modality).strip()
        for modality in understanding.get("modalities", ["text"])
        if str(modality).strip()
    ]
    available_modalities = [
        str(modality).strip()
        for modality in understanding.get("available_modalities", [])
        if str(modality).strip()
    ]
    question_text = " ".join(
        str(value or "")
        for value in (
            question,
            understanding.get("question"),
            understanding.get("query"),
        )
    ).lower()
    return {
        "question_type": _question_type(task_type, question_text, modalities),
        "task_type": task_type,
        "visual_intent": has_explicit_visual_intent(question_text)
        or bool(set(modalities) & VISUAL_MODALITIES),
        "element_intent": _has_term(question_text, ELEMENT_INTENT_TERMS)
        or bool(set(modalities) & ELEMENT_MODALITIES),
        "structured_calculation": _has_term(question_text, CALCULATION_TERMS),
        "graph_intent": task_type in SUMMARY_TASK_TYPES
        or _has_term(question_text, {"compare", "global", "overview", "summarize"}),
        "available_modalities": available_modalities,
        "scope": str(understanding.get("scope") or "document"),
    }


def _question_type(task_type: str, question_text: str, modalities: list[str]) -> str:
    if task_type in SUMMARY_TASK_TYPES:
        return task_type
    if (
        _has_term(question_text, ELEMENT_INTENT_TERMS)
        or set(modalities) & ELEMENT_MODALITIES
    ):
        return "table_lookup"
    if has_explicit_visual_intent(question_text) or set(modalities) & VISUAL_MODALITIES:
        return "visual_lookup"
    if _has_term(question_text, CALCULATION_TERMS):
        return "calculation"
    if question_text.startswith(
        ("did ", "does ", "do ", "is ", "are ", "was ", "were ")
    ):
        return "yes_no"
    return "qa"


def _normalized_route_probe(
    route_probe: dict[str, Any], features: dict[str, Any]
) -> dict[str, Any]:
    has_visual_probe = "visual" in route_probe
    probe = {
        name: _normalize_probe_item(route_probe.get(name))
        for name in ("text", "visual", "element", "graph")
    }
    if not any(item["evidence_count"] for item in probe.values()):
        probe["text"]["evidence_count"] = 1
        probe["text"]["locator_quality"] = 0.7
        probe["text"]["has_text_or_ocr"] = True
        if features["visual_intent"] and (
            not has_visual_probe or probe["visual"]["backend_healthy"]
        ):
            probe["visual"]["evidence_count"] = 1
            probe["visual"]["locator_quality"] = 0.7
            probe["visual"]["backend_healthy"] = True
    return probe


def _normalize_probe_item(value: Any) -> dict[str, Any]:
    item = dict(value or {}) if isinstance(value, dict) else {}
    return {
        "evidence_count": int(item.get("evidence_count") or 0),
        "top_score": _bounded_score(item.get("top_score")),
        "top_margin": _bounded_score(item.get("top_margin")),
        "locator_quality": _bounded_score(item.get("locator_quality")),
        "top_pages": _string_list(item.get("top_pages")),
        "top_sources": _string_list(item.get("top_sources")),
        "has_text_or_ocr": bool(item.get("has_text_or_ocr")),
        "backend_healthy": bool(item.get("backend_healthy", True)),
    }


def _route_confidences(
    probe: dict[str, dict[str, Any]], features: dict[str, Any]
) -> dict[str, float]:
    text = probe["text"]
    visual = probe["visual"]
    element = probe["element"]
    graph = probe["graph"]
    return {
        "text": _confidence(
            text,
            base=0.45,
            intent_bonus=0.0,
            text_bonus=0.08 if text["has_text_or_ocr"] else 0.0,
        ),
        "visual": _confidence(
            visual,
            base=0.35,
            intent_bonus=0.12 if features["visual_intent"] else 0.0,
            text_bonus=0.05 if visual["has_text_or_ocr"] else 0.0,
        ),
        "element": _confidence(
            element,
            base=0.35,
            intent_bonus=0.15 if features["element_intent"] else 0.0,
            text_bonus=0.05 if element["has_text_or_ocr"] else 0.0,
        ),
        "graph": _confidence(
            graph,
            base=0.3,
            intent_bonus=0.2 if features["graph_intent"] else 0.0,
            text_bonus=0.0,
        ),
    }


def _confidence(
    item: dict[str, Any],
    *,
    base: float,
    intent_bonus: float,
    text_bonus: float,
) -> float:
    if int(item["evidence_count"]) <= 0:
        return 0.0
    score = (
        base
        + min(int(item["evidence_count"]), 3) * 0.04
        + float(item["top_score"]) * 0.14
        + float(item["top_margin"]) * 0.08
        + float(item["locator_quality"]) * 0.16
        + intent_bonus
        + text_bonus
    )
    if not item["backend_healthy"]:
        score -= 0.25
    return round(max(0.0, min(score, 1.0)), 4)


def _route_scores(
    expected_quality: dict[str, float],
    expected_cost: dict[str, float],
) -> dict[str, float]:
    routes = set(expected_quality) | set(expected_cost)
    return {
        route: round(
            max(0.0, expected_quality.get(route, 0.0) - expected_cost.get(route, 0.0)),
            4,
        )
        for route in routes
    }


def _expected_route_quality(
    features: dict[str, Any],
    confidences: dict[str, float],
    probe: dict[str, dict[str, Any]],
    dataset_family: str,
) -> dict[str, float]:
    text = confidences["text"]
    visual = confidences["visual"]
    element = confidences["element"]
    graph = confidences["graph"]
    hybrid_allowed = _hybrid_allowed(confidences, features)
    dataset = dataset_text(dataset_family, {})
    element_coverage_ok = _element_coverage_ok(probe["element"])
    quality = {
        "doc_text": 0.15 + text,
        "doc_page_image": 0.1 + visual,
        "doc_element": 0.1 + element if element_coverage_ok else 0.0,
        "graph_global": 0.05 + graph,
        "hybrid": 0.2 + (text + max(visual, element)) / 2 if hybrid_allowed else 0.0,
    }
    if features["visual_intent"]:
        quality["doc_page_image"] += 0.32
        quality["doc_text"] -= 0.08
    if features["element_intent"]:
        if element_coverage_ok:
            quality["doc_element"] += 0.25
        quality["hybrid"] += 0.1 if hybrid_allowed else 0.0
    if features["structured_calculation"]:
        quality["doc_text"] += 0.1
        quality["hybrid"] += 0.12 if hybrid_allowed else 0.0
        if element_coverage_ok:
            quality["doc_element"] += 0.15
    if features["graph_intent"]:
        quality["graph_global"] += 0.35
    else:
        quality["graph_global"] -= 0.25
    if text >= 0.65 and not features["visual_intent"]:
        quality["doc_text"] += 0.25
        quality["doc_page_image"] -= 0.2
        quality["hybrid"] -= 0.1
    if is_mmdocrag_dataset(dataset) and not features["visual_intent"]:
        quality["doc_text"] += 0.2
        quality["doc_page_image"] -= 0.2
        quality["hybrid"] -= 0.12
    if "finance" in dataset and features["structured_calculation"]:
        quality["doc_text"] += 0.2
        quality["hybrid"] -= 0.05
    return {key: round(max(0.0, value), 4) for key, value in quality.items()}


def _expected_route_cost(
    features: dict[str, Any],
    confidences: dict[str, float],
    probe: dict[str, dict[str, Any]],
    dataset_family: str,
    latency_budget: dict[str, Any],
) -> dict[str, float]:
    del confidences
    dataset = dataset_text(dataset_family, latency_budget)
    cost = {
        "doc_text": 0.05,
        "doc_page_image": 0.45,
        "doc_element": 0.15,
        "graph_global": 0.1,
        "hybrid": 0.35,
    }
    if features["visual_intent"]:
        cost["doc_page_image"] -= 0.18
    if features["element_intent"] and _element_coverage_ok(probe["element"]):
        cost["doc_element"] -= 0.05
    if is_mmdocrag_dataset(dataset):
        cost["doc_page_image"] += 0.22
        cost["hybrid"] += 0.18
    if not latency_budget.get("vlm_generator_available", True):
        if features["visual_intent"]:
            cost["doc_page_image"] += 0.05
        else:
            cost["doc_page_image"] += 0.25
        cost["hybrid"] += 0.12
    return {key: round(max(0.0, value), 4) for key, value in cost.items()}


def _skipped_expensive_routes(
    features: dict[str, Any],
    confidences: dict[str, float],
    probe: dict[str, dict[str, Any]],
    dataset_family: str,
    expected_quality: dict[str, float],
    expected_cost: dict[str, float],
) -> list[str]:
    skipped: list[str] = []
    dataset = dataset_text(dataset_family, {})
    if (
        is_mmdocrag_dataset(dataset)
        and confidences["text"] >= 0.65
        and not features["visual_intent"]
    ):
        skipped.extend(["doc_page_image", "hybrid"])
    if not _element_coverage_ok(probe["element"]):
        skipped.append("doc_element")
    for route, cost in expected_cost.items():
        if (
            route in {"doc_page_image", "hybrid"}
            and cost >= 0.55
            and expected_quality.get(route, 0.0)
            <= expected_quality.get("doc_text", 0.0)
            and route not in skipped
        ):
            skipped.append(route)
    return skipped


def _element_coverage_ok(item: dict[str, Any]) -> bool:
    return (
        int(item["evidence_count"]) > 0
        and float(item["locator_quality"]) >= 0.5
        and bool(item["has_text_or_ocr"])
    )


def _hybrid_allowed(confidences: dict[str, float], features: dict[str, Any]) -> bool:
    if features["graph_intent"]:
        return False
    return confidences["text"] >= 0.45 and (
        confidences["visual"] >= 0.45 or confidences["element"] >= 0.45
    )


def _allowed_routes(value: Any) -> list[str]:
    return [str(item).strip() for item in value or [] if str(item).strip()]


def _has_term(text: str, terms: set[str]) -> bool:
    tokens = set(re.findall(r"[a-zA-Z0-9]+", str(text or "").lower()))
    return bool(tokens & terms)


def _unique(values: Any) -> list[str]:
    output: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in output:
            output.append(item)
    return output


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, (list, tuple, set)):
        return []
    return _unique(value)
