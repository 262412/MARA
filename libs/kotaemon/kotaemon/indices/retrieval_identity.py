from __future__ import annotations

import re
import unicodedata
from typing import Any

from kotaemon.base import RetrievedDocument

from .performance_cache import content_hash

_TOKEN_RE = re.compile(r"\s+")
SCORE_TIE_PRECISION_DECIMALS = 6
CANONICAL_TIE_BREAKER = "canonical_retrieval_identity"


def reciprocal_rank_fuse(
    vector_docs: list[RetrievedDocument],
    text_docs: list[RetrievedDocument],
    k: int = 60,
) -> list[RetrievedDocument]:
    if not vector_docs:
        return text_docs
    if not text_docs:
        return vector_docs

    ranked_paths = (
        canonicalize_ranked_documents(vector_docs),
        canonicalize_ranked_documents(text_docs),
    )
    fused_scores: dict[str, float] = {}
    fused_docs: dict[str, RetrievedDocument] = {}
    best_ranks: dict[str, int] = {}
    for documents in ranked_paths:
        for rank, document in enumerate(documents, start=1):
            key = fusion_key(document, fused_docs)
            fused_scores[key] = fused_scores.get(key, 0.0) + 1 / (k + rank)
            current = fused_docs.get(key)
            current_rank = best_ranks.get(key)
            keep = current is None or (current_rank is not None and rank < current_rank)
            if current is not None and rank == current_rank:
                keep = len(document.metadata) > len(current.metadata)
            if keep:
                fused_docs[key] = (
                    merge_retrieval_documents(document, current)
                    if current is not None
                    else document
                )
                best_ranks[key] = rank
            elif current is not None:
                fused_docs[key] = merge_retrieval_documents(current, document)
    return sorted(
        (_with_score(fused_docs[key], score) for key, score in fused_scores.items()),
        key=stable_retrieval_sort_key,
    )


def stable_retrieval_sort_key(document: RetrievedDocument) -> tuple[float, str]:
    return (
        -round(float(document.score or 0.0), SCORE_TIE_PRECISION_DECIMALS),
        canonical_retrieval_identity(document),
    )


def canonical_retrieval_identity(document: RetrievedDocument) -> str:
    return str(
        document.retrieval_metadata.get("canonical_id") or _canonical_id(document)
    )


def stable_scored_documents(
    documents: list[RetrievedDocument],
) -> list[RetrievedDocument]:
    return sorted(documents, key=stable_retrieval_sort_key)


def deterministic_ranking_contract() -> dict[str, Any]:
    return {
        "score_tie_precision_decimals": SCORE_TIE_PRECISION_DECIMALS,
        "tie_breaker": CANONICAL_TIE_BREAKER,
    }


def canonicalize_ranked_documents(
    documents: list[RetrievedDocument],
) -> list[RetrievedDocument]:
    selected: list[RetrievedDocument] = []
    for document in documents:
        prepared = _with_identity_metadata(document)
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(selected)
                if documents_are_duplicates(existing, prepared)
            ),
            None,
        )
        if duplicate_index is None:
            selected.append(prepared)
        else:
            selected[duplicate_index] = merge_retrieval_documents(
                selected[duplicate_index], prepared
            )
    return selected


def fusion_key(
    document: RetrievedDocument,
    fused_documents: dict[str, RetrievedDocument],
) -> str:
    for key, existing in fused_documents.items():
        if documents_are_duplicates(existing, document):
            return key
    return str(document.retrieval_metadata.get("canonical_id") or document.doc_id)


def documents_are_duplicates(
    left: RetrievedDocument,
    right: RetrievedDocument,
) -> bool:
    left_structure = _structure_key(left)
    right_structure = _structure_key(right)
    if left_structure and left_structure == right_structure:
        return True
    left_hash = _text_hash(left)
    return bool(left_hash and left_hash == _text_hash(right))


def merge_retrieval_documents(
    primary: RetrievedDocument,
    duplicate: RetrievedDocument,
) -> RetrievedDocument:
    merged = _clone(primary)
    metadata = dict(merged.retrieval_metadata)
    duplicate_metadata = dict(duplicate.retrieval_metadata)
    metadata["duplicate_doc_ids"] = _unique(
        list(metadata.get("duplicate_doc_ids") or [])
        + list(duplicate_metadata.get("duplicate_doc_ids") or [])
        + ([duplicate.doc_id] if duplicate.doc_id != primary.doc_id else [])
    )
    metadata["source_backrefs"] = _unique(
        list(metadata.get("source_backrefs") or [])
        + list(duplicate_metadata.get("source_backrefs") or [])
    )
    merged.retrieval_metadata = metadata
    return merged


def _with_identity_metadata(document: RetrievedDocument) -> RetrievedDocument:
    prepared = _clone(document)
    metadata = dict(prepared.retrieval_metadata)
    metadata["canonical_id"] = _canonical_id(prepared)
    metadata["duplicate_doc_ids"] = list(metadata.get("duplicate_doc_ids") or [])
    metadata["source_backrefs"] = _unique(
        list(metadata.get("source_backrefs") or []) + _document_backrefs(prepared)
    )
    prepared.retrieval_metadata = metadata
    return prepared


def _canonical_id(document: RetrievedDocument) -> str:
    structure = _structure_key(document)
    if structure:
        return ":".join(structure)
    text_hash = _text_hash(document)
    return f"text:{text_hash}" if text_hash else f"document:{document.doc_id}"


def _structure_key(document: RetrievedDocument) -> tuple[str, ...] | None:
    metadata = dict(document.metadata or {})
    source = str(
        metadata.get("file_id")
        or metadata.get("source_id")
        or metadata.get("document_id")
        or ""
    ).strip()
    element = str(metadata.get("element_id") or "").strip()
    if source and element:
        return ("element", source, element)
    table = str(metadata.get("table_id") or "").strip()
    row = metadata.get("row_index")
    column = metadata.get("column_index")
    if source and table and row is not None and column is not None:
        return ("cell", source, table, str(row), str(column))
    return None


def _text_hash(document: RetrievedDocument) -> str:
    text = unicodedata.normalize("NFKC", str(document.text or "")).lower().strip()
    normalized = _TOKEN_RE.sub(" ", text)
    return content_hash(normalized) if normalized else ""


def _document_backrefs(document: RetrievedDocument) -> list[str]:
    metadata = dict(document.metadata or {})
    source = str(
        metadata.get("file_id")
        or metadata.get("source_id")
        or metadata.get("document_id")
        or ""
    ).strip()
    page = str(metadata.get("page_label") or metadata.get("page_number") or "").strip()
    if not source:
        return []
    return [f"{source}#page:{page}" if page else f"{source}#source"]


def _clone(document: RetrievedDocument) -> RetrievedDocument:
    cloned = RetrievedDocument(**document.to_dict())
    cloned.retrieval_metadata = dict(document.retrieval_metadata or {})
    return cloned


def _with_score(document: RetrievedDocument, score: float) -> RetrievedDocument:
    scored = _clone(document)
    scored.score = score
    return scored


def _unique(values: list[Any]) -> list[str]:
    return list(
        dict.fromkeys(str(value).strip() for value in values if str(value).strip())
    )
