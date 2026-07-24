from __future__ import annotations

import re
from typing import Any

from .docqa_evidence_projection import (
    evidence_pages,
    evidence_sources,
    metadata_page_coverage,
    metadata_page_coverage_sources,
    retrieved_hits_from_docqa_evidence,
)
from .docqa_runtime_sources import (
    canonicalize_docqa_citations,
    canonicalize_docqa_hits,
    selected_source_fallback_hits,
)
from .engine_context import extract_citations
from .indexed_citations import indexed_inline_citations
from .schemas import BenchmarkDocument

_PAGE_RE = re.compile(r"(?:#page:|page[:\s]+)([\w.-]+)", flags=re.IGNORECASE)


def response_evidence_outputs(
    *,
    response: Any,
    documents: list[BenchmarkDocument],
    selected_file_ids: list[str],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[str],
    list[str],
    list[int | str],
]:
    evidence_bundle = dict(getattr(response, "evidence_bundle", {}) or {})
    evidence_metadata = dict(getattr(response, "evidence_metadata", {}) or {})
    retrieved_hits = retrieved_hits_from_docqa_evidence(
        evidence_bundle,
        evidence_metadata,
    )
    reference_citations = canonicalize_docqa_citations(
        extract_citations(response.references_text),
        documents,
        selected_file_ids,
    )
    answer_citations = canonicalize_docqa_citations(
        extract_citations(getattr(response, "answer", "")),
        documents,
        selected_file_ids,
    )
    reference_pages = _PAGE_RE.findall(response.references_text or "")
    if not retrieved_hits and not reference_citations and not reference_pages:
        retrieved_hits = selected_source_fallback_hits(documents, selected_file_ids)
    retrieved_hits = canonicalize_docqa_hits(
        retrieved_hits,
        documents,
        selected_file_ids,
    )
    predicted_citations = list(answer_citations)
    predicted_citations.extend(
        citation
        for citation in indexed_inline_citations(response.answer, retrieved_hits)
        if citation not in predicted_citations
    )
    predicted_sources = evidence_sources(retrieved_hits)
    predicted_sources.extend(
        source for source in reference_citations if source not in predicted_sources
    )
    predicted_sources.extend(
        source
        for source in metadata_page_coverage_sources(
            evidence_metadata,
            documents,
            selected_file_ids,
        )
        if source not in predicted_sources
    )
    predicted_pages: list[int | str] = list(evidence_pages(retrieved_hits))
    predicted_pages.extend(
        page for page in reference_pages if page not in predicted_pages
    )
    predicted_pages.extend(
        page
        for page in metadata_page_coverage(evidence_metadata)
        if page not in predicted_pages
    )
    return (
        evidence_metadata,
        retrieved_hits,
        predicted_sources,
        predicted_citations,
        predicted_pages,
    )
