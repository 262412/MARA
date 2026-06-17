from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class DatasetCapabilities:
    answer_correctness: bool
    page_evidence: bool
    span_evidence: bool
    citation_quality: bool
    hallucination_labels: bool
    multi_document: bool
    multimodal: bool
    source_level_citations: bool
    supports_abstention: bool


@dataclass(frozen=True, slots=True)
class DatasetProfile:
    dataset_family: str
    capabilities: DatasetCapabilities
    allowed_routes: tuple[str, ...]
    allowed_text_routes: tuple[str, ...]
    allowed_multimodal_routes: tuple[str, ...]


TEXT_ROUTES = ("doc_text", "hybrid", "graph_global")
MULTIMODAL_ROUTES = (
    "doc_text",
    "hybrid",
    "doc_page_image",
    "doc_element",
    "graph_global",
)


def profile_for_manifest(
    dataset_name: str,
    *,
    examples: Iterable[object],
) -> DatasetProfile:
    family = _dataset_family(dataset_name)
    inferred_multidoc = _has_multi_document_examples(examples)
    if family == "ragtruth":
        return _profile(
            family,
            answer_correctness=False,
            page_evidence=False,
            span_evidence=True,
            citation_quality=False,
            hallucination_labels=True,
            multi_document=inferred_multidoc,
            multimodal=False,
            source_level_citations=True,
            supports_abstention=True,
        )
    if family in {"alce", "qasper"}:
        return _profile(
            family,
            answer_correctness=True,
            page_evidence=False,
            span_evidence=True,
            citation_quality=True,
            hallucination_labels=False,
            multi_document=True,
            multimodal=False,
            source_level_citations=True,
            supports_abstention=False,
        )
    if family in {"mmdocrag", "slidevqa", "vidore"}:
        return _profile(
            family,
            answer_correctness=True,
            page_evidence=True,
            span_evidence=True,
            citation_quality=True,
            hallucination_labels=False,
            multi_document=inferred_multidoc,
            multimodal=True,
            source_level_citations=False,
            supports_abstention=False,
        )
    return _profile(
        family,
        answer_correctness=True,
        page_evidence=True,
        span_evidence=True,
        citation_quality=True,
        hallucination_labels=False,
        multi_document=inferred_multidoc,
        multimodal=False,
        source_level_citations=False,
        supports_abstention=False,
    )


def profile_for_dataset(dataset_name: str) -> DatasetProfile:
    return profile_for_manifest(dataset_name, examples=())


def _profile(
    dataset_family: str,
    *,
    answer_correctness: bool,
    page_evidence: bool,
    span_evidence: bool,
    citation_quality: bool,
    hallucination_labels: bool,
    multi_document: bool,
    multimodal: bool,
    source_level_citations: bool,
    supports_abstention: bool,
) -> DatasetProfile:
    return DatasetProfile(
        dataset_family=dataset_family,
        capabilities=DatasetCapabilities(
            answer_correctness=answer_correctness,
            page_evidence=page_evidence,
            span_evidence=span_evidence,
            citation_quality=citation_quality,
            hallucination_labels=hallucination_labels,
            multi_document=multi_document,
            multimodal=multimodal,
            source_level_citations=source_level_citations,
            supports_abstention=supports_abstention,
        ),
        allowed_routes=MULTIMODAL_ROUTES,
        allowed_text_routes=TEXT_ROUTES,
        allowed_multimodal_routes=MULTIMODAL_ROUTES,
    )


def _dataset_family(dataset_name: str) -> str:
    value = str(dataset_name or "").strip().lower()
    for family in (
        "financebench",
        "qasper",
        "ragtruth",
        "alce",
        "mmdocrag",
        "slidevqa",
        "vidore",
    ):
        if family in value:
            return family
    return value or "unknown"


def _has_multi_document_examples(examples: Iterable[object]) -> bool:
    for example in examples:
        document_ids = getattr(example, "document_ids", None)
        if document_ids and len(document_ids) > 1:
            return True
    return False
