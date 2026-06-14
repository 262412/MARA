from __future__ import annotations

import re
from pathlib import Path

_PAGE_TEXT_CACHE: dict[tuple[Path, tuple[int, ...]], list[tuple[int, str]]] = {}


def align_financebench_page(
    document_path: Path | None,
    page: int | str | None,
    span: str,
) -> tuple[int | str | None, str]:
    if document_path is None or page is None or not span:
        return page, ""

    needle = _normalize_financebench_span(span)
    if not needle:
        return page, ""

    for parser_page, text in _cached_candidate_pdf_pages(document_path, page):
        if needle in _normalize_financebench_span(text):
            if parser_page == page:
                return page, ""
            return parser_page, "financebench_span_to_parser_page"
    return page, ""


def _cached_candidate_pdf_pages(
    path: Path,
    page: int | str,
) -> list[tuple[int, str]]:
    page_numbers = _parser_page_candidates(page)
    if not page_numbers:
        return []
    cache_key = (path.resolve(), page_numbers)
    if cache_key not in _PAGE_TEXT_CACHE:
        _PAGE_TEXT_CACHE[cache_key] = extract_pdf_pages(
            path,
            page_numbers=page_numbers,
        )
    return _PAGE_TEXT_CACHE[cache_key]


def _parser_page_candidates(page: int | str) -> tuple[int, ...]:
    try:
        center = int(str(page).strip())
    except ValueError:
        return ()
    start = max(1, center - 2)
    end = max(start, center + 2)
    return tuple(range(start, end + 1))


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


def _normalize_financebench_span(value: str) -> str:
    return " ".join(re.findall(r"[a-zA-Z0-9]+", str(value or "").lower()))
