from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class NormalizedEvidence:
    document_id: str | None
    page_label: str | None
    page_index: int | None
    source: str | None
    span_text: str | None
    element_id: str | None
    modality: str | None
    support_label: str | None

    @property
    def source_id(self) -> str | None:
        return self.document_id or _citation_source_id(self.source)

    @property
    def citation(self) -> str | None:
        return self.source

    @property
    def text_span(self) -> str | None:
        return self.span_text

    @property
    def parser_page_index(self) -> int | None:
        return self.page_index

    @property
    def locator_kind(self) -> str:
        if self.page_label is not None:
            return "page"
        if self.element_id is not None:
            return "element"
        return "source"


def normalize_gold_evidence(example: Any) -> list[NormalizedEvidence]:
    rows = [
        dict(item)
        for item in list(getattr(example, "gold_evidence", []) or [])
        if isinstance(item, dict)
    ]
    pages = list(getattr(example, "evidence_pages", []) or [])
    sources = list(getattr(example, "evidence_sources", []) or [])
    if not rows:
        rows = [{} for _index in range(max(len(pages), len(sources), 1))]
    return [
        _normalized_evidence_row(
            row,
            page=pages[index] if index < len(pages) else None,
            source=sources[index] if index < len(sources) else None,
        )
        for index, row in enumerate(rows)
    ]


def normalize_gold_evidence_record(record: dict[str, Any]) -> NormalizedEvidence:
    return _normalized_evidence_row(record, page=None, source=None)


def _normalized_evidence_row(
    row: dict[str, Any],
    *,
    page: Any,
    source: Any,
) -> NormalizedEvidence:
    row_source = _first_text(row, "source", "citation", "id")
    fallback_source = _text_or_none(source)
    fallback_page = _text_or_none(page)
    document_id = _first_text(row, "document_id", "doc_id")
    row_page = (
        _page_label(row)
        or _locator_page_label(fallback_page)
        or fallback_page
        or _locator_page_label(row_source)
        or _locator_page_label(fallback_source)
    )
    citation = row_source if row_source is not None else fallback_source
    if citation is None and document_id is not None:
        citation = (
            f"{document_id}#page:{row_page}"
            if row_page is not None
            else f"{document_id}#source"
        )
    return NormalizedEvidence(
        document_id=document_id,
        page_label=row_page,
        page_index=_page_index(row),
        source=citation,
        span_text=_first_text(row, "text", "span", "quote", "evidence"),
        element_id=_first_text(row, "element_id", "element"),
        modality=_first_text(row, "modality", "type"),
        support_label=_first_text(row, "label", "support_label", "verdict"),
    )


def _first_text(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        text = _text_or_none(value)
        if text is not None:
            return text
    return None


def _text_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _page_label(row: dict[str, Any]) -> str | None:
    value = row.get("page_label", row.get("page"))
    text = _text_or_none(value)
    return _locator_page_label(text) or text


def _page_index(row: dict[str, Any]) -> int | None:
    text = _text_or_none(row.get("page_index"))
    if text is None:
        return None
    return int(text)


def _locator_page_label(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    patterns = (
        r"(?:^|[#\s:_-])page\s*[:=]?\s*(\d+)\b",
        r"\bp\.\s*(\d+)\b",
        r"\.[A-Za-z0-9]+:(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _citation_source_id(citation: str | None) -> str | None:
    text = str(citation or "").strip()
    if not text:
        return None
    return text.split("#", 1)[0] or None
