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
    canonicalize_docqa_evidence_metadata,
    canonicalize_docqa_hits,
    selected_source_fallback_hits,
)
from .engine_context import extract_citations
from .indexed_citations import indexed_inline_citations
from .qasper_evidence_identity import stabilize_qasper_evidence_projection
from .schemas import BenchmarkDocument

_PAGE_RE = re.compile(
    r"#page:(?P<explicit>[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?)"
    r"|\bpage(?:\s+|:\s*)(?P<numeric>\d+(?:[.-]\d+)?)\b",
    flags=re.IGNORECASE,
)


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
    evidence_bundle, evidence_metadata = _canonicalize_response_evidence(
        response,
        evidence_bundle=evidence_bundle,
        evidence_metadata=evidence_metadata,
        documents=documents,
        selected_file_ids=selected_file_ids,
    )
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
    reference_pages = _reference_pages(response.references_text or "")
    if not retrieved_hits and not reference_citations and not reference_pages:
        retrieved_hits = selected_source_fallback_hits(documents, selected_file_ids)
    retrieved_hits = canonicalize_docqa_hits(
        retrieved_hits,
        documents,
        selected_file_ids,
    )
    if _qasper_projection_required(evidence_bundle, evidence_metadata):
        evidence_metadata, retrieved_hits = stabilize_qasper_evidence_projection(
            evidence_metadata,
            retrieved_hits,
        )
        bundle_metadata, bundle_items = stabilize_qasper_evidence_projection(
            dict(evidence_bundle.get("metadata") or {}),
            list(evidence_bundle.get("items") or []),
        )
        evidence_bundle["metadata"] = bundle_metadata
        evidence_bundle["items"] = bundle_items
        response.evidence_metadata = evidence_metadata
        response.evidence_bundle = evidence_bundle
    predicted_sources, predicted_citations, predicted_pages = _predicted_outputs(
        response=response,
        evidence_metadata=evidence_metadata,
        retrieved_hits=retrieved_hits,
        reference_citations=reference_citations,
        answer_citations=answer_citations,
        reference_pages=reference_pages,
        documents=documents,
        selected_file_ids=selected_file_ids,
    )
    return (
        evidence_metadata,
        retrieved_hits,
        predicted_sources,
        predicted_citations,
        predicted_pages,
    )


def _predicted_outputs(
    *,
    response: Any,
    evidence_metadata: dict[str, Any],
    retrieved_hits: list[dict[str, Any]],
    reference_citations: list[str],
    answer_citations: list[str],
    reference_pages: list[str],
    documents: list[BenchmarkDocument],
    selected_file_ids: list[str],
) -> tuple[list[str], list[str], list[int | str]]:
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
    return predicted_sources, predicted_citations, predicted_pages


def _canonicalize_response_evidence(
    response: Any,
    *,
    evidence_bundle: dict[str, Any],
    evidence_metadata: dict[str, Any],
    documents: list[BenchmarkDocument],
    selected_file_ids: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence_metadata = canonicalize_docqa_evidence_metadata(
        evidence_metadata,
        documents,
        selected_file_ids,
    )
    bundle_metadata = evidence_bundle.get("metadata")
    if isinstance(bundle_metadata, dict):
        evidence_bundle["metadata"] = canonicalize_docqa_evidence_metadata(
            bundle_metadata,
            documents,
            selected_file_ids,
        )
    try:
        response.evidence_bundle = evidence_bundle
        response.evidence_metadata = evidence_metadata
    except AttributeError:
        pass
    return evidence_bundle, evidence_metadata


def _reference_pages(value: str) -> list[str]:
    pages: list[str] = []
    for match in _PAGE_RE.finditer(str(value or "")):
        page = str(match.group("explicit") or match.group("numeric") or "")
        if page and page not in pages:
            pages.append(page)
    return pages


def _qasper_projection_required(
    evidence_bundle: dict[str, Any],
    evidence_metadata: dict[str, Any],
) -> bool:
    bundle_metadata = evidence_bundle.get("metadata")
    metadata_values = (
        evidence_metadata,
        bundle_metadata if isinstance(bundle_metadata, dict) else {},
    )
    for metadata in metadata_values:
        plan = metadata.get("query_plan")
        if not isinstance(plan, dict):
            continue
        constraints = plan.get("constraints")
        if (
            isinstance(constraints, dict)
            and str(constraints.get("verification_domain") or "").casefold() == "qasper"
        ):
            return True
    return False
