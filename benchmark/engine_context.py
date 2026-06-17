from __future__ import annotations

import re
from typing import Any

_CITATION_RE = re.compile(
    r"(?<![\\w/-])([A-Za-z0-9_.:/-]+#(?:page:[A-Za-z0-9_.-]+|source|evidence:[A-Za-z0-9_.:-]+))"
)


def extract_text(item: Any) -> str:
    for key in ("text", "content", "page_text", "full_text"):
        value = _field_value(item, key, None)
        if value:
            return str(value)

    pages = document_pages(item)
    if pages:
        page_texts = [extract_text(page) for page in pages]
        return "\n\n".join(text for text in page_texts if text)

    return ""


def document_pages(document: Any) -> list[Any]:
    pages = _field_value(document, "pages", None)
    if pages is None:
        return []
    return list(pages)


def join_document_texts(documents: list[Any]) -> str:
    texts = [extract_text(document) for document in documents]
    return "\n\n".join(text for text in texts if text)


def parsed_indexes_to_context(parsed_indexes: list[Any], wanted_pages=None) -> str:
    wanted = {str(page).strip() for page in wanted_pages or [] if str(page).strip()}
    chunks: list[str] = []
    for parsed_index in parsed_indexes:
        for document in parsed_index.parsed_documents:
            page = normalize_page(
                document.metadata.get("page_label")
                or document.metadata.get("page_number")
                or document.metadata.get("page")
            )
            if wanted and page not in wanted:
                continue
            text = str(getattr(document, "text", "") or "").strip()
            if not text:
                continue
            label = f"[{parsed_index.document.document_id}"
            if page:
                label += f" page {page}"
            label += "]"
            chunks.append(f"{label}\n{text}")
    return "\n\n".join(chunks)


def all_context_pages(parsed_indexes: list[Any]) -> list[str]:
    pages: list[str] = []
    for parsed_index in parsed_indexes:
        for document in parsed_index.parsed_documents:
            page = normalize_page(
                document.metadata.get("page_label")
                or document.metadata.get("page_number")
                or document.metadata.get("page")
            )
            if page and page not in pages:
                pages.append(page)
    return pages


def evidence_page_set(example: Any) -> set[str]:
    pages = {
        normalize_page(page) for page in _field_value(example, "evidence_pages", [])
    }
    for evidence in _field_value(example, "gold_evidence", []):
        page = _field_value(evidence, "page", None)
        if page is None:
            page = _field_value(evidence, "page_number", None)
        if page is not None:
            pages.add(normalize_page(page))
    return {page for page in pages if page}


def first_evidence_page(example: Any) -> int | None:
    for page in _field_value(example, "evidence_pages", []):
        parsed = _int_page(page)
        if parsed is not None:
            return parsed
    for evidence in _field_value(example, "gold_evidence", []):
        page = _field_value(evidence, "page", None)
        if page is None:
            page = _field_value(evidence, "page_number", None)
        parsed = _int_page(page)
        if parsed is not None:
            return parsed
    return None


def normalize_page(page: Any) -> str:
    return str(page).strip()


def extract_citations(text: str) -> list[str]:
    citations: list[str] = []
    for match in _CITATION_RE.finditer(str(text or "")):
        citation = match.group(1).strip().rstrip(".,;:)]}")
        if citation and citation not in citations:
            citations.append(citation)
    return citations


def _field_value(item: Any, key: str, default: Any) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _int_page(page: Any) -> int | None:
    try:
        return int(str(page).strip())
    except (TypeError, ValueError):
        return None
