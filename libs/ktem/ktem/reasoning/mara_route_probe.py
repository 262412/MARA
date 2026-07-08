from __future__ import annotations

from typing import Any

from .mara_route_retrieval import route_retrieval_metadata
from .mara_route_scorer import route_probe_from_metadata


def controller_route_probe(
    pipeline: Any,
    message: str,
    history: list,
    understanding: dict[str, Any],
) -> dict[str, Any]:
    if not _should_build_controller_route_probe(pipeline):
        return {}
    probe: dict[str, Any] = {}
    if _should_probe_text_route(pipeline, understanding) and (
        _route_allowed(pipeline, "doc_text") or _route_allowed(pipeline, "hybrid")
    ):
        text_metadata = route_retrieval_metadata(
            pipeline,
            "text_rag",
            message,
            history,
            understanding,
            text_retrieve=lambda: pipeline.retrieve(message, history),
            metadata_builder=pipeline.build_evidence_metadata,
        )
        probe["text"] = route_probe_from_metadata("text", text_metadata)
    if _should_probe_visual_route(pipeline, understanding, probe) and (
        _route_allowed(pipeline, "doc_page_image") or _route_allowed(pipeline, "hybrid")
    ):
        page_metadata = route_retrieval_metadata(
            pipeline,
            "page_image_rag",
            message,
            history,
            understanding,
            text_retrieve=lambda: ([], []),
            metadata_builder=lambda _docs, _understanding: {},
        )
        probe["visual"] = route_probe_from_metadata(
            "visual",
            page_metadata,
            backend_healthy=page_image_route_available(pipeline),
        )
    if _route_allowed(pipeline, "doc_element") or _route_allowed(pipeline, "hybrid"):
        element_metadata = route_retrieval_metadata(
            pipeline,
            "element_rag",
            message,
            history,
            understanding,
            text_retrieve=lambda: ([], []),
            metadata_builder=lambda _docs, _understanding: {},
        )
        probe["element"] = route_probe_from_metadata("element", element_metadata)
    if _route_allowed(pipeline, "graph_global"):
        graph_metadata = route_retrieval_metadata(
            pipeline,
            "graph_rag",
            message,
            history,
            understanding,
            text_retrieve=lambda: ([], []),
            metadata_builder=lambda _docs, _understanding: {},
        )
        probe["graph"] = route_probe_from_metadata("graph", graph_metadata)
    return probe


def controller_latency_budget(pipeline: Any) -> dict[str, Any]:
    family = dataset_family(pipeline)
    return {
        "dataset_family": family,
        "visual_retriever_available": page_image_route_available(pipeline),
        "vlm_generator_available": getattr(pipeline, "vlm_generator", None) is not None,
        "text_protect": "mmdocrag" in family.lower(),
    }


def dataset_family(pipeline: Any) -> str:
    for name in ("dataset_family", "retrieval_domain", "verification_domain"):
        value = str(getattr(pipeline, name, "") or "").strip()
        if value:
            return value
    return ""


def page_image_route_available(pipeline: Any) -> bool:
    allowed_routes = [
        str(route).strip()
        for route in getattr(pipeline, "allowed_routes", None) or []
        if str(route).strip()
    ]
    if allowed_routes and not any(
        route in {"doc_page_image", "hybrid"} for route in allowed_routes
    ):
        return False
    return bool(
        getattr(pipeline, "visual_retriever_backend", None)
        or getattr(pipeline, "visual_retriever", None)
        or getattr(pipeline, "page_image_index_records", None)
    )


def _should_build_controller_route_probe(pipeline: Any) -> bool:
    controller_mode = str(getattr(pipeline, "controller_mode", "") or "llm").lower()
    route_policy = str(getattr(pipeline, "route_policy", "") or "auto").lower()
    return controller_mode in {"", "llm"} and route_policy in {"", "auto"}


def _route_allowed(pipeline: Any, route: str) -> bool:
    allowed = [
        str(item).strip()
        for item in getattr(pipeline, "allowed_routes", None) or []
        if str(item).strip()
    ]
    return not allowed or route in allowed


def _should_probe_text_route(pipeline: Any, understanding: dict[str, Any]) -> bool:
    planner = getattr(pipeline, "planner", None)
    planner_model = getattr(pipeline, "planner_model", None)
    if (
        callable(planner)
        and not planner_model
        and _understanding_has_visual_intent(understanding)
    ):
        return False
    return True


def _understanding_has_visual_intent(understanding: dict[str, Any]) -> bool:
    modalities = {
        str(modality).strip()
        for modality in understanding.get("modalities", [])
        if str(modality).strip()
    }
    if modalities & {"figure", "image", "page_image", "slide"}:
        return True
    question = str(understanding.get("question") or "").lower()
    return any(
        term in question
        for term in (
            "chart",
            "diagram",
            "figure",
            "graph",
            "image",
            "picture",
            "shown",
            "slide",
            "visual",
            "visible",
        )
    )


def _should_probe_visual_route(
    pipeline: Any,
    understanding: dict[str, Any],
    probe: dict[str, Any],
) -> bool:
    if not page_image_route_available(pipeline):
        return False
    if _understanding_has_visual_intent(understanding):
        return True
    if "mmdocrag" not in dataset_family(pipeline).lower():
        return True
    text_probe = dict(probe.get("text") or {})
    if not text_probe:
        return True
    return not _text_probe_is_confident(text_probe)


def _text_probe_is_confident(text_probe: dict[str, Any]) -> bool:
    try:
        evidence_count = int(text_probe.get("evidence_count") or 0)
        locator_quality = float(text_probe.get("locator_quality") or 0.0)
    except (TypeError, ValueError):
        return False
    return (
        evidence_count > 0
        and locator_quality >= 0.5
        and bool(text_probe.get("has_text_or_ocr"))
    )
