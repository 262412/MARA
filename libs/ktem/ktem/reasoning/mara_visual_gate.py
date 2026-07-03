from __future__ import annotations

from typing import Any

VISUAL_GENERATION_TERMS = (
    "chart",
    "diagram",
    "figure",
    "image",
    "layout",
    "plot",
    "shown",
    "slide",
    "visual",
    "visible",
)


def hybrid_should_use_visual_generator(request: Any, decision: Any, bundle: Any) -> bool:
    if not _bundle_has_page_image_evidence(bundle):
        return False
    if not _bundle_has_text_evidence(bundle):
        bundle.metadata["visual_generation_gate"] = "visual_only_evidence"
        return True
    prompt = " ".join(
        [
            str(getattr(request, "prompt", "") or ""),
            str(getattr(decision, "reason", "") or ""),
        ]
    ).lower()
    if any(term in prompt for term in VISUAL_GENERATION_TERMS):
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
