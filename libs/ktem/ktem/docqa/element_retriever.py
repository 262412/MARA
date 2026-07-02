from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Protocol


class ElementRetrieverBackend(Protocol):
    name: str

    def score(self, query: str, record: dict[str, Any]) -> float:
        ...


class LocalElementRetriever:
    name = "local_element_retriever"
    backend_type = "deterministic_metadata"

    def score(self, query: str, record: dict[str, Any]) -> float:
        query_tokens = _tokens(query)
        if not query_tokens:
            return 0.0
        element_tokens = _tokens(
            " ".join(
                [
                    *(
                        str(record.get(key) or "")
                        for key in (
                            "element_id",
                            "element_type",
                            "modality",
                            "caption",
                            "text",
                        )
                    ),
                    *_metadata_alias_text(record),
                ]
            )
        )
        return round(len(query_tokens & element_tokens) / len(query_tokens), 4)


def rank_element_records(
    query: str,
    records: list[dict[str, Any]],
    *,
    retriever: ElementRetrieverBackend | None = None,
    evidence_hints: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    backend = retriever or LocalElementRetriever()
    hints = _normalize_hints(evidence_hints)
    scored = [
        (_score_record(backend, query, record, hints), index, record)
        for index, record in enumerate(records)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    scores = {
        str(record.get("evidence_id") or "").strip(): score
        for score, _, record in scored
        if str(record.get("evidence_id") or "").strip()
    }
    ranked = [
        _with_score_metadata(
            record,
            score,
            backend.name,
            getattr(backend, "backend_type", "custom"),
            _hint_matches(record, hints),
        )
        for score, _, record in scored
    ]
    return ranked, scores


def _score_record(
    backend: ElementRetrieverBackend,
    query: str,
    record: dict[str, Any],
    hints: dict[str, set[str]],
) -> float:
    score = float(backend.score(query, record) or 0.0)
    matches = _hint_matches(record, hints)
    if matches["source"]:
        score += 1.0
    if matches["page"]:
        score += 3.0
    if matches["element_type"]:
        score += 0.5
    return round(score, 4)


def _with_score_metadata(
    record: dict[str, Any],
    score: float,
    retriever_name: str,
    backend_type: str,
    matches: dict[str, bool],
) -> dict[str, Any]:
    updated = deepcopy(record)
    metadata = dict(updated.get("metadata") or {})
    metadata["element_retriever"] = retriever_name
    metadata["element_retriever_backend_type"] = backend_type
    metadata["element_retriever_score"] = score
    metadata["element_retriever_page_hint_match"] = matches["page"]
    metadata["element_retriever_source_hint_match"] = matches["source"]
    metadata["element_retriever_type_hint_match"] = matches["element_type"]
    updated["metadata"] = metadata
    return updated


def _normalize_hints(value: dict[str, Any] | None) -> dict[str, set[str]]:
    value = value or {}
    return {
        "pages": {_normalize_page(item) for item in value.get("pages") or []},
        "source_ids": {_normalize_text(item) for item in value.get("source_ids") or []},
        "element_types": {
            _normalize_element_type(item) for item in value.get("element_types") or []
        },
    }


def _hint_matches(
    record: dict[str, Any], hints: dict[str, set[str]]
) -> dict[str, bool]:
    pages = {
        _normalize_page(record.get("page_label")),
        _normalize_page(record.get("page")),
        _normalize_page(record.get("page_number")),
    }
    source_ids = {
        _normalize_text(record.get("source_id")),
        _normalize_text(record.get("file_id")),
        _normalize_text(record.get("document_id")),
        _normalize_source_name(record.get("file_name")),
        _normalize_source_name(record.get("source_name")),
    }
    element_types = _record_element_types(record)
    return {
        "page": bool((pages - {""}) & hints["pages"]),
        "source": bool((source_ids - {""}) & hints["source_ids"]),
        "element_type": bool((element_types - {""}) & hints["element_types"]),
    }


def _record_element_types(record: dict[str, Any]) -> set[str]:
    metadata = dict(record.get("metadata") or {})
    values: list[Any] = [
        record.get("element_type"),
        record.get("modality"),
        record.get("type"),
        record.get("element_type_aliases"),
        metadata.get("element_type_aliases"),
    ]
    return {
        _normalize_element_type(item)
        for value in values
        for item in _iter_values(value)
    }


def _metadata_alias_text(record: dict[str, Any]) -> list[str]:
    metadata = dict(record.get("metadata") or {})
    return [
        str(item)
        for value in (
            record.get("element_id_aliases"),
            record.get("element_type_aliases"),
            metadata.get("element_id_aliases"),
            metadata.get("element_type_aliases"),
        )
        for item in _iter_values(value)
        if str(item).strip()
    ]


def _iter_values(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _normalize_page(value: Any) -> str:
    text = _normalize_text(value)
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _normalize_source_name(value: Any) -> str:
    text = _normalize_text(value)
    return text.removesuffix(".pdf")


def _normalize_element_type(value: Any) -> str:
    element_type = _normalize_text(value)
    if element_type in {"image", "fig", "chart", "plot"}:
        return "figure"
    return element_type


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if len(token) > 2
    }
