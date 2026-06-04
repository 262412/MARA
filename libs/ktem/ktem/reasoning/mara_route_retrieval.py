from __future__ import annotations

from typing import Any, Callable

from ktem.docqa.graph_index import (
    graph_context_evidence_metadata,
    select_graph_index_evidence,
)
from ktem.docqa.multimodal_index import build_local_page_image_records
from ktem.docqa.visual_retriever import rank_page_image_records

TextRetrieveFn = Callable[[], tuple[list[Any], list[Any]]]
MetadataBuilderFn = Callable[[list[Any], dict[str, Any]], dict[str, Any]]


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
    return metadata_builder(docs, understanding)


def _page_image_metadata(
    pipeline: Any,
    understanding: dict[str, Any],
) -> dict[str, Any]:
    records = _page_image_records_for_pipeline(pipeline)
    if not records:
        return {
            "requested_modalities": list(understanding.get("modalities", [])),
            "modality_counts": {},
            "page_coverage": [],
            "source_ids": [],
            "evidence_ids": [],
            "evidence": [],
        }
    ranked, scores = rank_page_image_records(
        str(understanding.get("question") or ""),
        records,
    )
    return {
        "requested_modalities": list(understanding.get("modalities", [])),
        "modality_counts": {"page_image": len(ranked)},
        "page_coverage": _unique(item.get("page_label") for item in ranked),
        "source_ids": _unique(item.get("file_id") for item in ranked),
        "evidence_ids": _unique(item.get("evidence_id") for item in ranked),
        "evidence": [],
        "page_image_index": ranked,
        "visual_retriever_scores": scores,
        "visual_backend_type": _visual_backend_type(ranked),
    }


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
    return build_local_page_image_records(file_records, page_numbers=page_numbers)


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
        }
    return {
        "requested_modalities": list(understanding.get("modalities", [])),
        "modality_counts": _element_modality_counts(records),
        "page_coverage": _unique(item.get("page_label") for item in records),
        "source_ids": _unique(item.get("file_id") for item in records),
        "evidence_ids": _unique(item.get("evidence_id") for item in records),
        "evidence": [],
        "element_index": records,
    }


def _element_records_for_pipeline(pipeline: Any) -> list[dict[str, Any]]:
    explicit_records = getattr(pipeline, "element_index_records", None)
    if not explicit_records:
        return []
    return [dict(item) for item in explicit_records if isinstance(item, dict)]


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
