"""Shared, UI-independent document preview services."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "OfficeConversionService": (".office", "OfficeConversionService"),
    "OfficePreviewConversionService": (".office", "OfficePreviewConversionService"),
    "PageContext": (".context", "PageContext"),
    "PdfPage": (".pdf", "PdfPage"),
    "PdfService": (".pdf", "PdfService"),
    "PreviewCleanupError": (".errors", "PreviewCleanupError"),
    "PreviewContextError": (".errors", "PreviewContextError"),
    "PreviewConversionError": (".errors", "PreviewConversionError"),
    "PreviewError": (".errors", "PreviewError"),
    "PreviewErrorCode": (".errors", "PreviewErrorCode"),
    "PreviewPurpose": (".context", "PreviewPurpose"),
    "PreviewSourceError": (".errors", "PreviewSourceError"),
    "PreviewService": (".service", "PreviewService"),
    "canonical_office_cache_dir": (".service", "canonical_office_cache_dir"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
