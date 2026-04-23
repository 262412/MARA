from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol, Sequence, runtime_checkable

from .elements import DocumentElement

MultimodalPolicyMode = Literal["on_demand"]


@runtime_checkable
class OCRPlugin(Protocol):
    """OCR extension point for extracting text from figure/image content."""

    def extract_text(
        self,
        image: Any,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        """Return extracted text for an image, or an empty string when unavailable."""


@runtime_checkable
class VLMCaptionPlugin(Protocol):
    """VLM extension point for generating captions from figure/image content."""

    def caption_image(
        self,
        image: Any,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        """Return an image caption, or an empty string when unavailable."""


@runtime_checkable
class MathOCRPlugin(Protocol):
    """Math OCR extension point for recognizing formula images."""

    def recognize_formula(
        self,
        image: Any,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        """Return normalized formula text, or an empty string when unavailable."""


class NoOpOCRPlugin:
    """Default OCR plugin that never calls external services."""

    def extract_text(
        self,
        image: Any,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        return ""


class NoOpVLMCaptionPlugin:
    """Default VLM caption plugin that never calls external services."""

    def caption_image(
        self,
        image: Any,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        return ""


class NoOpMathOCRPlugin:
    """Default Math OCR plugin that never calls external services."""

    def recognize_formula(
        self,
        image: Any,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        return ""


@dataclass(frozen=True)
class MultimodalPluginPolicy:
    """Feature gates for optional multimodal processing.

    All plugins default to disabled. The only supported mode is on-demand:
    enabled plugins are recommended only when the query route and retrieved
    elements indicate that extra image/formula work may be useful.
    """

    enable_ocr: bool = False
    enable_vlm: bool = False
    enable_math_ocr: bool = False
    mode: MultimodalPolicyMode = "on_demand"


@dataclass(frozen=True)
class MultimodalPluginDecision:
    """Recommended multimodal plugin work for a retrieval result set."""

    run_ocr: bool
    run_vlm: bool
    run_math_ocr: bool
    ocr_element_ids: tuple[str, ...] = ()
    vlm_element_ids: tuple[str, ...] = ()
    math_ocr_element_ids: tuple[str, ...] = ()

    @property
    def candidate_element_ids(self) -> tuple[str, ...]:
        return _dedupe(
            self.ocr_element_ids + self.vlm_element_ids + self.math_ocr_element_ids
        )


def recommend_multimodal_plugins(
    query_route: Any,
    retrieved_docs: Sequence[Any],
    policy: MultimodalPluginPolicy | None = None,
) -> MultimodalPluginDecision:
    """Recommend optional multimodal plugins without executing any plugin.

    The recommendation is intentionally side-effect free. Callers can use the
    returned element ids to decide which externally configured plugins to invoke.
    """

    active_policy = policy or MultimodalPluginPolicy()
    modality = _route_modality(query_route)
    image_ids = _image_element_ids(retrieved_docs)
    formula_ids = _formula_image_ids_missing_normalized_formula(retrieved_docs)

    image_query = modality in {"figure", "image", "mixed"}
    formula_query = modality in {"formula", "mixed"}

    ocr_ids = image_ids if active_policy.enable_ocr and image_query else ()
    vlm_ids = image_ids if active_policy.enable_vlm and image_query else ()
    math_ocr_ids = (
        formula_ids if active_policy.enable_math_ocr and formula_query else ()
    )

    return MultimodalPluginDecision(
        run_ocr=bool(ocr_ids),
        run_vlm=bool(vlm_ids),
        run_math_ocr=bool(math_ocr_ids),
        ocr_element_ids=ocr_ids,
        vlm_element_ids=vlm_ids,
        math_ocr_element_ids=math_ocr_ids,
    )


def _route_modality(query_route: Any) -> str:
    if isinstance(query_route, str):
        return query_route.strip().lower()
    if isinstance(query_route, Mapping):
        return str(query_route.get("modality") or "text").strip().lower()
    return str(getattr(query_route, "modality", "text") or "text").strip().lower()


def _image_element_ids(retrieved_docs: Sequence[Any]) -> tuple[str, ...]:
    return tuple(
        element_id
        for doc in retrieved_docs
        if _element_type(doc) in {"figure", "image"}
        for element_id in (_element_id(doc),)
        if element_id
    )


def _formula_image_ids_missing_normalized_formula(
    retrieved_docs: Sequence[Any],
) -> tuple[str, ...]:
    ids: list[str] = []
    for doc in retrieved_docs:
        element_type = _element_type(doc)
        if element_type not in {"formula", "formula_image"}:
            continue
        if (
            not _has_value(_field(doc, "formula_image"))
            and element_type != "formula_image"
        ):
            continue
        if _has_value(_field(doc, "normalized_formula")):
            continue
        element_id = _element_id(doc)
        if element_id:
            ids.append(element_id)
    return tuple(ids)


def _element_type(doc: Any) -> str:
    value = _field(doc, "element_type")
    if value is None:
        value = _metadata_field(doc, "element_type", "type")
    return str(value or "text").strip().lower()


def _element_id(doc: Any) -> str | None:
    value = _field(doc, "element_id")
    if value is None:
        value = _metadata_field(doc, "element_id")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _field(doc: Any, key: str) -> Any:
    if isinstance(doc, DocumentElement):
        return getattr(doc, key)
    if isinstance(doc, Mapping):
        return doc.get(key)
    return getattr(doc, key, None)


def _metadata_field(doc: Any, *keys: str) -> Any:
    metadata = getattr(doc, "metadata", None)
    if not isinstance(metadata, Mapping):
        return None
    for key in keys:
        if key in metadata:
            return metadata[key]
    return None


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return tuple(deduped)


__all__ = [
    "MathOCRPlugin",
    "MultimodalPluginDecision",
    "MultimodalPluginPolicy",
    "NoOpMathOCRPlugin",
    "NoOpOCRPlugin",
    "NoOpVLMCaptionPlugin",
    "OCRPlugin",
    "VLMCaptionPlugin",
    "recommend_multimodal_plugins",
]
