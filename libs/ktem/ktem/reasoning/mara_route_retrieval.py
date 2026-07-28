from __future__ import annotations

import os
import re
from typing import Any, Callable

from ktem.docqa.element_retriever import rank_element_records
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.graph_index import (
    graph_context_evidence_metadata,
    select_graph_index_evidence,
)
from ktem.docqa.multimodal_index import build_local_page_image_records
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.required_slot_selection import required_slot_shortlist
from ktem.docqa.visual_retriever import rank_page_image_records

from .mara_element_ingestion_trace import element_ingestion_trace

TextRetrieveFn = Callable[[], tuple[list[Any], list[Any]]]
MetadataBuilderFn = Callable[[list[Any], dict[str, Any]], dict[str, Any]]
DEFAULT_PAGE_IMAGE_RANK_CANDIDATE_LIMIT = 48
ELEMENT_RANK_CANDIDATE_LIMIT = 20
_QUERY_STOPWORDS = {
    "and",
    "are",
    "between",
    "does",
    "from",
    "how",
    "is",
    "of",
    "on",
    "page",
    "show",
    "shown",
    "the",
    "this",
    "to",
    "what",
    "which",
}


def controller_text_retrieve(
    pipeline: Any,
    query: str,
    history: list,
) -> tuple[list[Any], list[Any]]:
    marker = "_mara_disable_nested_retrieval_retry"
    previous = getattr(pipeline, marker, None)
    setattr(pipeline, marker, True)
    try:
        return pipeline.retrieve(query, history)
    finally:
        if previous is None:
            delattr(pipeline, marker)
        else:
            setattr(pipeline, marker, previous)


def route_retrieval_metadata(
    pipeline: Any,
    route: str,
    message: str,
    history: list,
    understanding: dict[str, Any],
    *,
    text_retrieve: TextRetrieveFn,
    metadata_builder: MetadataBuilderFn,
) -> dict[str, Any]:
    if route == "page_image_rag":
        return _page_image_metadata(pipeline, understanding)
    if route == "element_rag":
        return _element_metadata(pipeline, understanding)
    if route == "graph_rag":
        return _graph_metadata(pipeline, understanding)
    if route == "hybrid_rag":
        metadata = _text_metadata(
            pipeline,
            message,
            history,
            understanding,
            text_retrieve=text_retrieve,
            metadata_builder=metadata_builder,
        )
        if _page_image_metadata_enabled(pipeline):
            _merge_page_image_metadata(
                metadata, _page_image_metadata(pipeline, understanding)
            )
        _merge_element_metadata(metadata, _element_metadata(pipeline, understanding))
        _merge_graph_metadata(metadata, _graph_metadata(pipeline, understanding))
        return metadata
    return _text_metadata(
        pipeline,
        message,
        history,
        understanding,
        text_retrieve=text_retrieve,
        metadata_builder=metadata_builder,
    )


def _text_metadata(
    pipeline: Any,
    message: str,
    history: list,
    understanding: dict[str, Any],
    *,
    text_retrieve: TextRetrieveFn,
    metadata_builder: MetadataBuilderFn,
) -> dict[str, Any]:
    docs, info = text_retrieve()
    pipeline._mara_cached_retrieval = (message, list(history), docs, info)
    metadata = metadata_builder(docs, understanding)
    attempts = _bounded_retrieval_attempts(
        getattr(pipeline, "_mara_retrieval_attempts", [])
    )
    if attempts:
        metadata["retrieval_attempts"] = attempts
    metadata["retrieval_info_count"] = len(info)
    return metadata


def _bounded_retrieval_attempts(attempts: Any) -> list[dict[str, Any]]:
    bounded: list[dict[str, Any]] = []
    for attempt in attempts or []:
        if not isinstance(attempt, dict):
            continue
        bounded.append(
            {
                "attempt": int(attempt.get("attempt") or 0),
                "evidence_count": int(attempt.get("evidence_count") or 0),
                "retry_reason": str(attempt.get("retry_reason") or ""),
            }
        )
    return bounded


def _page_image_metadata(
    pipeline: Any,
    understanding: dict[str, Any],
) -> dict[str, Any]:
    all_records = _page_image_records_for_pipeline(pipeline)
    records = _page_image_scoring_candidates(pipeline, understanding, all_records)
    if not records:
        return {
            "requested_modalities": list(understanding.get("modalities", [])),
            "modality_counts": {},
            "page_coverage": [],
            "source_ids": [],
            "evidence_ids": [],
            "evidence": [],
            "page_image_candidate_count": len(all_records),
            "page_image_scored_candidate_count": 0,
        }
    ranked, scores = rank_page_image_records(
        str(understanding.get("question") or ""),
        records,
        retriever=getattr(pipeline, "visual_retriever", None),
    )
    metadata = {
        "requested_modalities": list(understanding.get("modalities", [])),
        "modality_counts": {"page_image": len(ranked)},
        "page_coverage": _unique(item.get("page_label") for item in ranked),
        "source_ids": _unique(item.get("file_id") for item in ranked),
        "evidence_ids": _unique(item.get("evidence_id") for item in ranked),
        "evidence": [],
        "page_image_index": ranked,
        "visual_retriever_scores": scores,
        "visual_backend_type": _visual_backend_type(ranked),
        "page_image_candidate_count": len(all_records),
        "page_image_scored_candidate_count": len(records),
    }
    if len(records) < len(all_records):
        metadata["page_image_candidate_selection"] = "lightweight_text_overlap_cap"
    return metadata


def _page_image_metadata_enabled(pipeline: Any) -> bool:
    visual_retriever = getattr(pipeline, "visual_retriever", None)
    visual_backend = getattr(pipeline, "visual_retriever_backend", None)
    allowed_routes = {
        str(route).strip()
        for route in getattr(pipeline, "allowed_routes", None) or []
        if str(route).strip()
    }
    if allowed_routes and "doc_page_image" not in allowed_routes:
        route_policy = (
            str(getattr(pipeline, "route_policy", "") or "")
            .strip()
            .lower()
            .replace("-", "_")
        )
        if route_policy not in {"hybrid", "visual", "page_image"}:
            return False
        if not (visual_retriever or visual_backend):
            return False
    return bool(
        getattr(pipeline, "page_image_index_records", None)
        or visual_retriever
        or visual_backend
    )


def _page_image_records_for_pipeline(pipeline: Any) -> list[dict[str, Any]]:
    explicit_records = getattr(pipeline, "page_image_index_records", None)
    if explicit_records:
        return [dict(item) for item in explicit_records if isinstance(item, dict)]

    file_records = [
        dict(item)
        for item in getattr(pipeline, "selected_file_records", None) or []
        if isinstance(item, dict)
    ]
    if not file_records:
        return []

    active_file_id = str(getattr(pipeline, "active_file_id", "") or "").strip()
    if active_file_id:
        active_records = [
            item
            for item in file_records
            if str(item.get("file_id") or item.get("id") or "").strip()
            == active_file_id
        ]
        file_records = active_records or file_records

    page_number = getattr(pipeline, "page_number", None)
    page_numbers = None
    if page_number not in (None, ""):
        page_numbers = [int(str(page_number))]
    max_pages = None if page_numbers else _page_image_rank_candidate_limit(pipeline)
    return build_local_page_image_records(
        file_records,
        page_numbers=page_numbers,
        max_pages=max_pages,
    )


def _page_image_scoring_candidates(
    pipeline: Any,
    understanding: dict[str, Any],
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    limit = _page_image_rank_candidate_limit(pipeline)
    if limit <= 0 or len(records) <= limit:
        return records
    page_scoped = _page_scoped_records(pipeline, records)
    if page_scoped:
        return page_scoped[:limit]
    query_tokens = _query_tokens(str(understanding.get("question") or ""))
    ranked = sorted(
        (
            (
                _record_query_overlap(record, query_tokens),
                _record_has_text(record),
                -index,
                record,
            )
            for index, record in enumerate(records)
        ),
        reverse=True,
    )
    return [record for *_scores, record in ranked[:limit]]


def _page_image_rank_candidate_limit(pipeline: Any) -> int:
    raw_value = getattr(pipeline, "page_image_rank_candidate_limit", None)
    if raw_value in (None, ""):
        raw_value = os.getenv(
            "MARA_PAGE_IMAGE_RANK_CANDIDATE_LIMIT",
            str(DEFAULT_PAGE_IMAGE_RANK_CANDIDATE_LIMIT),
        )
    if raw_value is None:
        return DEFAULT_PAGE_IMAGE_RANK_CANDIDATE_LIMIT
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_PAGE_IMAGE_RANK_CANDIDATE_LIMIT


def _page_scoped_records(
    pipeline: Any,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    page_number = getattr(pipeline, "page_number", None)
    if page_number in (None, ""):
        return []
    page_label = str(page_number).strip()
    return [
        record
        for record in records
        if str(record.get("page_label") or record.get("page_number") or "").strip()
        == page_label
    ]


def _record_query_overlap(record: dict[str, Any], query_tokens: set[str]) -> int:
    if not query_tokens:
        return 0
    return len(_record_tokens(record) & query_tokens)


def _record_has_text(record: dict[str, Any]) -> bool:
    return bool(
        str(
            record.get("text") or record.get("ocr_text") or record.get("caption") or ""
        ).strip()
    )


def _record_tokens(record: dict[str, Any]) -> set[str]:
    metadata = dict(record.get("metadata") or {})
    values = [
        record.get("text"),
        record.get("ocr_text"),
        record.get("caption"),
        record.get("page_label"),
        record.get("file_name"),
        metadata.get("late_interaction_tokens"),
        metadata.get("multi_vector_representation"),
    ]
    return _query_tokens(" ".join(_string_values(values)))


def _query_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if len(token) > 2 and token not in _QUERY_STOPWORDS
    }


def _string_values(values: list[Any]) -> list[str]:
    strings: list[str] = []
    for value in values:
        if isinstance(value, (list, tuple, set)):
            strings.extend(str(item) for item in value)
            continue
        strings.append(str(value or ""))
    return strings


def _element_metadata(
    pipeline: Any,
    understanding: dict[str, Any],
) -> dict[str, Any]:
    records = _element_records_for_pipeline(pipeline)
    if not records:
        return {
            "requested_modalities": list(understanding.get("modalities", [])),
            "modality_counts": {},
            "page_coverage": [],
            "source_ids": [],
            "evidence_ids": [],
            "evidence": [],
            "element_candidate_count": 0,
            "element_selected_candidate_count": 0,
            "element_ingestion_trace": element_ingestion_trace(pipeline, records),
        }
    ranked, scores = rank_element_records(
        str(understanding.get("question") or ""),
        records,
        retriever=getattr(pipeline, "element_retriever", None),
        evidence_hints=_element_evidence_hints(understanding, pipeline),
    )
    request = getattr(pipeline, "docqa_request", None)
    plan = build_query_plan(
        str(understanding.get("question") or ""),
        answer_type=str(
            getattr(request, "answer_type", None)
            or getattr(request, "task_type", None)
            or ""
        ),
        verification_domain=str(getattr(request, "verification_domain", None) or ""),
        planner_payload=getattr(request, "query_plan", None),
    )
    selected, restored_required = required_slot_shortlist(
        ranked,
        plan,
        candidate_limit=ELEMENT_RANK_CANDIDATE_LIMIT,
    )
    selected_ids = {identity_of(item).key for item in selected}
    return {
        "requested_modalities": list(understanding.get("modalities", [])),
        "modality_counts": _element_modality_counts(selected),
        "page_coverage": _unique(item.get("page_label") for item in selected),
        "source_ids": _unique(item.get("file_id") for item in selected),
        "evidence_ids": _unique(item.get("evidence_id") for item in selected),
        "evidence": [],
        "element_index": selected,
        "element_retriever_scores": {
            evidence_id: score
            for evidence_id, score in scores.items()
            if evidence_id in selected_ids
        },
        "element_candidate_count": len(records),
        "element_selected_candidate_count": len(selected),
        "element_required_slot_candidates_restored": restored_required,
        "element_ingestion_trace": element_ingestion_trace(pipeline, records),
    }


def _element_records_for_pipeline(pipeline: Any) -> list[dict[str, Any]]:
    explicit_records = getattr(pipeline, "element_index_records", None)
    if not explicit_records:
        return []
    return [dict(item) for item in explicit_records if isinstance(item, dict)]


def _element_evidence_hints(
    understanding: dict[str, Any], pipeline: Any
) -> dict[str, list[Any]]:
    return {
        "pages": _hint_values(
            understanding.get("evidence_pages")
            or understanding.get("pages")
            or understanding.get("page_numbers")
            or _request_page_hint(pipeline)
        ),
        "source_ids": _hint_values(
            understanding.get("source_ids")
            or understanding.get("document_ids")
            or understanding.get("file_ids")
            or _request_source_hints(pipeline)
        ),
        "element_types": list(
            understanding.get("element_types")
            or understanding.get("modalities")
            or understanding.get("expected_modalities")
            or []
        ),
    }


def _request_page_hint(pipeline: Any) -> list[Any]:
    request = getattr(pipeline, "docqa_request", None)
    page_number = getattr(request, "page_number", None)
    if page_number in (None, ""):
        page_number = getattr(pipeline, "page_number", None)
    return [] if page_number in (None, "") else [page_number]


def _request_source_hints(pipeline: Any) -> list[Any]:
    request = getattr(pipeline, "docqa_request", None)
    selected = [
        item
        for item in getattr(request, "selected_file_ids", None) or []
        if str(item).strip()
    ]
    if selected:
        return selected
    active_file_id = getattr(request, "active_file_id", None) or getattr(
        pipeline, "active_file_id", None
    )
    return [] if active_file_id in (None, "") else [active_file_id]


def _hint_values(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _element_modality_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        modality = str(
            record.get("modality") or record.get("element_type") or "element"
        ).strip()
        counts[modality or "element"] = counts.get(modality or "element", 0) + 1
    return counts


def _merge_page_image_metadata(
    metadata: dict[str, Any], page_metadata: dict[str, Any]
) -> None:
    if not page_metadata.get("page_image_index"):
        return
    metadata["page_image_index"] = page_metadata["page_image_index"]
    metadata["visual_retriever_scores"] = page_metadata.get(
        "visual_retriever_scores", {}
    )
    metadata["visual_backend_type"] = page_metadata.get("visual_backend_type", "")
    metadata["page_coverage"] = _unique(
        list(metadata.get("page_coverage") or [])
        + list(page_metadata.get("page_coverage") or [])
    )
    metadata["source_ids"] = _unique(
        list(metadata.get("source_ids") or [])
        + list(page_metadata.get("source_ids") or [])
    )
    metadata["evidence_ids"] = _unique(
        list(metadata.get("evidence_ids") or [])
        + list(page_metadata.get("evidence_ids") or [])
    )


def _merge_element_metadata(
    metadata: dict[str, Any], element_metadata: dict[str, Any]
) -> None:
    if not element_metadata.get("element_index"):
        return
    metadata["element_index"] = list(element_metadata.get("element_index") or [])
    metadata["element_retriever_scores"] = dict(
        element_metadata.get("element_retriever_scores") or {}
    )
    metadata["page_coverage"] = _unique(
        list(metadata.get("page_coverage") or [])
        + list(element_metadata.get("page_coverage") or [])
    )
    metadata["source_ids"] = _unique(
        list(metadata.get("source_ids") or [])
        + list(element_metadata.get("source_ids") or [])
    )
    metadata["evidence_ids"] = _unique(
        list(metadata.get("evidence_ids") or [])
        + list(element_metadata.get("evidence_ids") or [])
    )


def _graph_metadata(pipeline: Any, understanding: dict[str, Any]) -> dict[str, Any]:
    graph_context = getattr(pipeline, "graph_context", None)
    if not isinstance(graph_context, dict):
        return {}
    indexed_metadata = select_graph_index_evidence(
        str(understanding.get("question") or ""),
        graph_context,
        graph_mode=getattr(pipeline, "graph_mode", None),
    )
    if indexed_metadata:
        return indexed_metadata
    return graph_context_evidence_metadata(
        graph_context,
        list(understanding.get("modalities", [])),
    )


def _merge_graph_metadata(
    metadata: dict[str, Any], graph_metadata: dict[str, Any]
) -> None:
    if not graph_metadata.get("graph_evidence"):
        return
    metadata["graph_backend"] = graph_metadata.get("graph_backend", "")
    metadata["graph_mode"] = graph_metadata.get("graph_mode", "")
    metadata["graph_evidence"] = list(graph_metadata.get("graph_evidence") or [])
    metadata["page_coverage"] = _unique(
        list(metadata.get("page_coverage") or [])
        + list(graph_metadata.get("page_coverage") or [])
    )
    metadata["source_ids"] = _unique(
        list(metadata.get("source_ids") or [])
        + list(graph_metadata.get("source_ids") or [])
    )
    metadata["evidence_ids"] = _unique(
        list(metadata.get("evidence_ids") or [])
        + list(graph_metadata.get("evidence_ids") or [])
    )


def _visual_backend_type(records: list[dict[str, Any]]) -> str:
    for record in records:
        metadata = dict(record.get("metadata") or {})
        backend = str(metadata.get("visual_backend_type") or "").strip()
        if backend:
            return backend
    return "local_smoke"


def _unique(values: Any) -> list[str]:
    output: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in output:
            output.append(item)
    return output
