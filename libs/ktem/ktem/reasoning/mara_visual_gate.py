from __future__ import annotations

from typing import Any

from .mara_visual_intent import has_explicit_visual_intent


def hybrid_should_use_visual_generator(
    request: Any, decision: Any, bundle: Any
) -> bool:
    if not _bundle_has_page_image_evidence(bundle):
        return False
    if not _bundle_has_text_evidence(bundle):
        bundle.metadata["visual_generation_gate"] = "visual_only_evidence"
        return True
    if _text_strong_mmdocrag_request(request, decision):
        bundle.metadata["visual_generation_gate"] = "skipped_text_strong"
        _record_skipped_expensive_route(bundle, "doc_page_image")
        return False
    if _visual_margin_too_low(decision):
        bundle.metadata["visual_generation_gate"] = "skipped_low_visual_margin"
        _record_skipped_expensive_route(bundle, "doc_page_image")
        return False
    prompt = " ".join(
        [
            str(getattr(request, "prompt", "") or ""),
            str(getattr(decision, "reason", "") or ""),
        ]
    ).lower()
    if has_explicit_visual_intent(prompt):
        bundle.metadata["visual_generation_gate"] = "visual_intent"
        return True
    bundle.metadata["visual_generation_gate"] = "skipped_text_strong"
    return False


def _bundle_has_page_image_evidence(bundle: Any) -> bool:
    return any(
        isinstance(item, dict) and str(item.get("modality") or "") == "page_image"
        for item in getattr(bundle, "items", []) or []
    )


def _bundle_has_text_evidence(bundle: Any) -> bool:
    return any(
        isinstance(item, dict)
        and str(item.get("modality") or "") == "text"
        and str(item.get("text") or "").strip()
        for item in getattr(bundle, "items", []) or []
    )


def _text_strong_mmdocrag_request(request: Any, decision: Any) -> bool:
    domain = str(getattr(request, "verification_domain", "") or "").strip().lower()
    if "mmdocrag" not in domain:
        return False
    return _route_confidence(decision, "text") >= 0.65


def _visual_margin_too_low(decision: Any) -> bool:
    visual_confidence = _route_confidence(decision, "visual")
    if visual_confidence <= 0.0:
        return False
    visual_probe = dict(getattr(decision, "route_probe", {}) or {}).get("visual") or {}
    try:
        margin = float(dict(visual_probe).get("top_margin") or 0.0)
    except (TypeError, ValueError):
        margin = 0.0
    return visual_confidence < 0.6 or margin < 0.08


def _route_confidence(decision: Any, key: str) -> float:
    try:
        value = dict(getattr(decision, "route_confidences", {}) or {}).get(key)
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _record_skipped_expensive_route(bundle: Any, route: str) -> None:
    skipped = [
        str(item)
        for item in bundle.metadata.get("skipped_expensive_routes") or []
        if str(item).strip()
    ]
    if route not in skipped:
        skipped.append(route)
    bundle.metadata["skipped_expensive_routes"] = skipped
