from __future__ import annotations

import logging

from docx.exceptions import PythonDocxError
from docx.oxml.exceptions import XmlchemyError

from .docx_package import DocxPackageReader, docx_error
from .docx_pagination import paginate_docx_html
from .docx_render import DocxHtmlRenderer
from .errors import PreviewError, PreviewErrorCode

logger = logging.getLogger(__name__)


def extract_docx_text_strict(file_path: str, max_chars: int = 9000) -> str:
    return DocxPackageReader(file_path).extract_text(max_chars=max_chars)


def extract_docx_html_strict(file_path: str, max_chars: int = 12000) -> str:
    reader = DocxPackageReader(file_path)
    document = reader.load_document()
    try:
        return DocxHtmlRenderer(document).render(max_chars=max_chars)
    except (
        AttributeError,
        IndexError,
        KeyError,
        PythonDocxError,
        TypeError,
        ValueError,
        XmlchemyError,
    ) as exc:
        raise docx_error(
            PreviewErrorCode.SOURCE_INVALID,
            reader.source_path,
            "docx_render",
            f"DOCX content is malformed and cannot be rendered: {exc}",
        ) from exc


def extract_docx_text(file_path: str, max_chars: int = 9000) -> str:
    try:
        return extract_docx_text_strict(file_path, max_chars=max_chars)
    except PreviewError as exc:
        _log_compatibility_fallback(exc)
        return ""


def extract_docx_html(file_path: str, max_chars: int = 12000) -> str:
    try:
        return extract_docx_html_strict(file_path, max_chars=max_chars)
    except PreviewError as exc:
        _log_compatibility_fallback(exc)
        return ""


def _log_compatibility_fallback(error: PreviewError) -> None:
    logger.warning(
        "DOCX preview fallback: code=%s stage=%s file=%s converter=%s "
        "reason=%s details=%s",
        error.code.value,
        error.stage,
        error.source_path,
        error.converter,
        error.reason,
        error.details,
    )


__all__ = [
    "extract_docx_html",
    "extract_docx_html_strict",
    "extract_docx_text",
    "extract_docx_text_strict",
    "paginate_docx_html",
]
