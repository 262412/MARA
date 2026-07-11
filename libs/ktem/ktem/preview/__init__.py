"""Shared, UI-independent document preview services."""

from .context import PageContext, PreviewPurpose
from .errors import (
    PreviewCleanupError,
    PreviewContextError,
    PreviewConversionError,
    PreviewError,
    PreviewErrorCode,
    PreviewSourceError,
)
from .office import OfficeConversionService, OfficePreviewConversionService
from .pdf import PdfPage, PdfService
from .service import PreviewService, canonical_office_cache_dir

__all__ = [
    "OfficeConversionService",
    "OfficePreviewConversionService",
    "PageContext",
    "PdfPage",
    "PdfService",
    "PreviewCleanupError",
    "PreviewConversionError",
    "PreviewContextError",
    "PreviewError",
    "PreviewErrorCode",
    "PreviewPurpose",
    "PreviewSourceError",
    "PreviewService",
    "canonical_office_cache_dir",
]
