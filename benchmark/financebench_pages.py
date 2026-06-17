from __future__ import annotations

from pathlib import Path

from .page_alignment import align_span_to_parser_page

_PAGE_TEXT_CACHE: dict[tuple[Path, tuple[int, ...]], list[tuple[int, str]]] = {}


def align_financebench_page(
    document_path: Path | None,
    page: int | str | None,
    span: str,
) -> tuple[int | str | None, str]:
    aligned_page, alignment = align_span_to_parser_page(
        document_path,
        page,
        span,
        extract_pages=_cached_candidate_pdf_pages,
    )
    if alignment == "span_to_parser_page":
        return aligned_page, "financebench_span_to_parser_page"
    return aligned_page, alignment


def _cached_candidate_pdf_pages(
    path: Path,
    page_numbers: tuple[int, ...],
) -> list[tuple[int, str]]:
    if not page_numbers:
        return []
    cache_key = (path.resolve(), page_numbers)
    if cache_key not in _PAGE_TEXT_CACHE:
        _PAGE_TEXT_CACHE[cache_key] = extract_pdf_pages(
            path,
            page_numbers=page_numbers,
        )
    return _PAGE_TEXT_CACHE[cache_key]


def extract_pdf_pages(
    path: Path,
    *,
    page_numbers: tuple[int, ...] | None = None,
) -> list[tuple[int, str]]:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError:
        return []

    try:
        reader = PdfReader(str(path))
        requested = set(page_numbers or ())
        return [
            (index + 1, page.extract_text() or "")
            for index, page in enumerate(reader.pages)
            if not requested or index + 1 in requested
        ]
    except (OSError, RuntimeError, ValueError, PdfReadError):
        return []
