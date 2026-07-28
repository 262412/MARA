from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .evidence_field_values import (
    atomic_identity_fields,
    item_metadata_text,
    representation_values,
    retrieval_lineage_values,
)
from .evidence_identity import (
    EVIDENCE_BUNDLE_SCHEMA_VERSION,
    canonicalize_and_dedupe_evidence,
    identity_of,
)
from .evidence_locators import merged_locator_metadata, source_alias_values
from .evidence_planning import select_planned_evidence
from .evidence_ranking_trace import materialize_reranked_candidates
from .evidence_schema import EvidenceBundle, EvidenceElement
from .graph_evidence import graph_items
from .hybrid_fusion import fuse_hybrid_evidence
from .m3docrag import select_page_first_evidence
from .query_planning import (
    ensure_request_query_plan,
    request_planning_question,
    retrieval_budget,
)
from .required_slot_selection import required_slot_shortlist

MAX_RERANK_CANDIDATES = 80


@dataclass(frozen=True)
class _EvidenceStages:
    canonical_candidates: list[dict[str, Any]]
    ranked_candidates: list[dict[str, Any]]
    reranker_input: list[dict[str, Any]]
    reranked: list[dict[str, Any]] | None
    selection_candidates: list[dict[str, Any]]
    dedupe_trace: dict[str, Any]
    ranking_metadata: dict[str, object]
    required_slot_restored: int
    page_ranking_trace: dict[str, Any] | None
    fusion_trace: dict[str, Any] | None
    reranker_trace: dict[str, Any] | None


def build_evidence_bundle(
    route: str,
    request: Any,
    evidence_metadata: dict[str, Any],
) -> EvidenceBundle:
    query_plan = ensure_request_query_plan(request)
    items = _initial_evidence_items(route, request, evidence_metadata)
    stages = _build_evidence_stages(
        route,
        request,
        evidence_metadata,
        items,
        query_plan,
    )
    deduped = stages.selection_candidates
    deduped, planning_metadata = select_planned_evidence(request, deduped)
    metadata = dict(evidence_metadata)
    metadata["schema_version"] = EVIDENCE_BUNDLE_SCHEMA_VERSION
    metadata["dedupe_trace"] = stages.dedupe_trace
    metadata["canonical_candidate_count"] = len(stages.canonical_candidates)
    metadata["canonical_candidate_evidence"] = stages.canonical_candidates
    metadata["candidate_evidence"] = stages.canonical_candidates
    metadata["candidate_ranked_evidence"] = stages.ranked_candidates
    metadata["candidate_ranking_contract"] = "global_ranked_v1"
    metadata[
        "pre_rerank_required_slot_candidates_restored"
    ] = stages.required_slot_restored
    metadata["reranker_input_evidence"] = stages.reranker_input
    metadata["reranker_input_contract"] = "required_slot_restored.v1"
    if route == "hybrid":
        metadata["fused_evidence"] = stages.ranked_candidates
    if stages.reranked is not None:
        metadata["reranked_candidate_count"] = len(stages.reranked)
        metadata["reranked_evidence"] = stages.reranked
    metadata["ranking_trace"] = stages.ranking_metadata
    metadata.update(merged_locator_metadata(metadata, deduped))
    metadata["modality_counts"] = dict(Counter(item["modality"] for item in deduped))
    metadata["evidence"] = deduped
    metadata["selected_evidence"] = deduped
    metadata["generation_context_evidence"] = deduped
    metadata["used_evidence"] = deduped
    metadata["stage_aliases"] = {
        "used_evidence": "generation_context_evidence",
    }
    metadata.update(planning_metadata)
    if stages.page_ranking_trace is not None:
        metadata["m3docrag_trace"] = stages.page_ranking_trace
    if stages.fusion_trace is not None:
        metadata["hybrid_fusion_trace"] = stages.fusion_trace
    if stages.reranker_trace is not None:
        metadata["hybrid_reranker_trace"] = stages.reranker_trace
    return EvidenceBundle(route=route, items=deduped, metadata=metadata)


def _build_evidence_stages(
    route: str,
    request: Any,
    evidence_metadata: dict[str, Any],
    items: list[dict[str, Any]],
    query_plan: Any,
) -> _EvidenceStages:
    deduped, dedupe_trace = canonicalize_and_dedupe_evidence(items)
    canonical_candidates = list(deduped)
    planning_question = request_planning_question(request)
    fusion_trace = None
    if route == "hybrid":
        deduped, fusion_trace = fuse_hybrid_evidence(
            planning_question,
            canonical_candidates,
            strategy=str(evidence_metadata.get("hybrid_fusion_strategy") or ""),
            domain=getattr(request, "verification_domain", None),
        )
    ranked_candidates = list(deduped)
    reranker_input, restored = required_slot_shortlist(
        ranked_candidates,
        query_plan,
        candidate_limit=MAX_RERANK_CANDIDATES,
    )
    reranker_scored = reranker_input
    reranker_trace = None
    hybrid_reranker = evidence_metadata.get("hybrid_fusion_ranker")
    if route == "hybrid" and hybrid_reranker is not None:
        reranker_scored, reranker_trace = fuse_hybrid_evidence(
            planning_question,
            reranker_input,
            learned_ranker=hybrid_reranker,
            domain=getattr(request, "verification_domain", None),
        )
    reranked, ranking_metadata = materialize_reranked_candidates(
        reranker_scored,
        evidence_metadata,
        limit=30,
    )
    selection_candidates = _reranked_with_remaining_candidates(
        reranked,
        reranker_input,
    )
    page_ranking_trace = None
    if route == "hybrid":
        selection_candidates, page_ranking_trace = select_page_first_evidence(
            planning_question,
            selection_candidates,
            max_pages=retrieval_budget(query_plan)["max_pages"],
        )
    return _EvidenceStages(
        canonical_candidates=canonical_candidates,
        ranked_candidates=ranked_candidates,
        reranker_input=reranker_input,
        reranked=reranked,
        selection_candidates=selection_candidates,
        dedupe_trace=dedupe_trace,
        ranking_metadata=ranking_metadata,
        required_slot_restored=restored,
        page_ranking_trace=page_ranking_trace,
        fusion_trace=fusion_trace,
        reranker_trace=reranker_trace,
    )


def _initial_evidence_items(
    route: str,
    request: Any,
    evidence_metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    base_items = [
        _coerce_item(item) for item in evidence_metadata.get("evidence") or []
    ]
    items = (
        [] if route in {"doc_page_image", "doc_element", "graph_global"} else base_items
    )
    if route in {"doc", "hybrid"} and not base_items:
        selected_text_item = _selected_text_item(request, route)
        if selected_text_item is not None:
            items.append(selected_text_item)
    if route in {"doc_page_image", "hybrid"}:
        page_items = _page_image_items(evidence_metadata)
        page_item = _page_image_item(request, route)
        if page_item is not None:
            page_items.append(page_item)
        items.extend(_rank_route_items(page_items, request, "doc_page_image"))
    if _uses_element_index(route, request):
        element_scores = dict(evidence_metadata.get("element_retriever_scores") or {})
        element_items = [
            _coerce_item(
                _with_retriever_score(
                    item,
                    element_scores,
                    "element_retriever_score",
                )
            )
            for item in evidence_metadata.get("element_index") or []
        ]
        element_items.extend(
            _coerce_item(item) for item in evidence_metadata.get("elements") or []
        )
        items.extend(_rank_route_items(element_items, request, "doc_element"))
    if route in {"graph_global", "hybrid"}:
        items.extend(graph_items(request, evidence_metadata))
    return items


def _uses_element_index(route: str, request: Any) -> bool:
    if route in {"doc_element", "hybrid"}:
        return True
    if route not in {"doc", "doc_text"}:
        return False
    plan = ensure_request_query_plan(request)
    return bool(plan.constraints.get("requires_structure"))


def _page_image_items(evidence_metadata: dict[str, Any]) -> list[dict[str, Any]]:
    scores = dict(evidence_metadata.get("visual_retriever_scores") or {})
    return [
        _coerce_item(_with_retriever_score(item, scores, "visual_retriever_score"))
        for item in evidence_metadata.get("page_image_index") or []
    ]


def _with_retriever_score(
    item: dict[str, Any],
    scores: dict[str, Any],
    metadata_key: str,
) -> dict[str, Any]:
    score_keys = (
        identity_of(item).key,
        str(item.get("cell_id") or "").strip(),
        str(item.get("evidence_id") or "").strip(),
        str(item.get("canonical_id") or "").strip(),
        str(item.get("element_id") or "").strip(),
    )
    score_key = next((key for key in score_keys if key and key in scores), "")
    if not score_key:
        return item
    scored = dict(item)
    metadata = dict(scored.get("metadata") or {})
    metadata[metadata_key] = float(scores[score_key])
    scored["metadata"] = metadata
    return scored


def _coerce_item(item: dict[str, Any]) -> dict[str, Any]:
    metadata = _merged_item_metadata(item)
    file_id, page_label, modality, backrefs = _coerced_locator_fields(
        item,
        metadata,
    )
    return EvidenceElement(
        evidence_id=str(item.get("evidence_id") or item.get("doc_id") or "").strip(),
        source_id=file_id,
        source_name=str(
            item.get("file_name")
            or item.get("source_name")
            or metadata.get("file_name")
            or metadata.get("source_name")
            or ""
        ).strip(),
        source_aliases=source_alias_values(item, metadata, file_id),
        page_label=page_label,
        dataset_page=str(
            item.get("dataset_page") or metadata.get("dataset_page") or ""
        ).strip(),
        parser_page_index=_optional_int(
            item.get("parser_page_index", metadata.get("parser_page_index"))
        ),
        page_aliases=_string_values(
            item.get("page_aliases") or metadata.get("page_aliases")
        ),
        modality=modality or "text",
        element_id=str(item.get("element_id") or "").strip(),
        **atomic_identity_fields(item, metadata),
        canonical_id=str(item.get("canonical_id") or "").strip(),
        parent_element_id=str(
            item.get("parent_element_id") or metadata.get("parent_element_id") or ""
        ).strip(),
        neighbor_element_ids=_string_values(
            item.get("neighbor_element_ids")
            or metadata.get("neighbor_element_ids")
            or metadata.get("neighbors")
        ),
        section_id=str(
            item.get("section_id") or metadata.get("section_id") or ""
        ).strip(),
        table_id=str(item.get("table_id") or metadata.get("table_id") or "").strip(),
        row_index=_optional_int(item.get("row_index", metadata.get("row_index"))),
        column_index=_optional_int(
            item.get("column_index", metadata.get("column_index"))
        ),
        row_label=str(item.get("row_label") or metadata.get("row_label") or "").strip(),
        column_label=str(
            item.get("column_label") or metadata.get("column_label") or ""
        ).strip(),
        period=str(item.get("period") or metadata.get("period") or "").strip(),
        period_kind=item_metadata_text(item, metadata, "period_kind"),
        value=item_metadata_text(item, metadata, "value"),
        unit=str(item.get("unit") or metadata.get("unit") or "").strip(),
        scale=str(item.get("scale") or metadata.get("scale") or "").strip(),
        currency=str(item.get("currency") or metadata.get("currency") or "").strip(),
        statement_kind=item_metadata_text(item, metadata, "statement_kind"),
        financial_scope=item_metadata_text(item, metadata, "financial_scope"),
        continuation_id=str(
            item.get("continuation_id")
            or metadata.get("continuation_id")
            or metadata.get("table_continuation_id")
            or ""
        ).strip(),
        chunk_start=_optional_int(item.get("chunk_start", metadata.get("chunk_start"))),
        chunk_end=_optional_int(item.get("chunk_end", metadata.get("chunk_end"))),
        normalized_text_hash=str(item.get("normalized_text_hash") or "").strip(),
        duplicate_evidence_ids=_string_values(item.get("duplicate_evidence_ids")),
        retrieval_lineage=retrieval_lineage_values(item, metadata),
        bbox=item.get("bbox"),
        caption=str(item.get("caption") or "").strip(),
        text=str(item.get("text") or item.get("content") or "").strip(),
        ocr_text=str(item.get("ocr_text") or "").strip(),
        vlm_text=str(item.get("vlm_text") or "").strip(),
        representations=representation_values(item, metadata),
        source_backrefs=backrefs,
        evidence_level=str(item.get("evidence_level") or "page").strip(),
        metadata=metadata,
    ).as_dict()


def _coerced_locator_fields(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[str, str, str, list[str]]:
    file_id = str(
        item.get("file_id")
        or item.get("source_id")
        or metadata.get("file_id")
        or metadata.get("source_id")
        or ""
    ).strip()
    page_label = str(
        item.get("page_label")
        or item.get("page")
        or metadata.get("page_label")
        or metadata.get("page_number")
        or metadata.get("page")
        or ""
    ).strip()
    modality = str(
        item.get("modality")
        or item.get("element_type")
        or item.get("type")
        or metadata.get("element_type")
        or metadata.get("type")
        or "text"
    ).strip()
    backrefs = _source_backrefs_from_item(item, metadata)
    if not backrefs and file_id and page_label:
        backrefs = [f"{file_id}#page:{page_label}"]
    return file_id, page_label, modality, backrefs


def _merged_item_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    nested = metadata.get("metadata")
    if isinstance(nested, dict):
        merged = dict(nested)
        merged.update(metadata)
        return merged
    return metadata


def _source_backrefs_from_item(
    item: dict[str, Any], metadata: dict[str, Any]
) -> list[str]:
    source = item.get("source_backrefs") or metadata.get("source_backrefs") or []
    if isinstance(source, str):
        return [source] if source else []
    return list(source)


def _page_image_item(request: Any, route: str) -> dict[str, Any] | None:
    file_id = str(getattr(request, "active_file_id", "") or "").strip()
    file_name = str(getattr(request, "active_file_name", "") or "").strip()
    page_number = getattr(request, "page_number", None)
    if not file_id or page_number is None or page_number == "":
        return None
    page_label = str(max(1, int(page_number)))
    text = str(getattr(request, "selected_text", "") or "").strip()
    return EvidenceElement(
        evidence_id=f"page-image:{file_id}:{page_label}",
        source_id=file_id,
        source_name=file_name,
        page_label=page_label,
        modality="page_image",
        text=text,
        ocr_text=text,
        source_backrefs=[f"{file_id}#page:{page_label}"],
        metadata={"route": route},
    ).as_dict()


def _selected_text_item(request: Any, route: str) -> dict[str, Any] | None:
    text = str(getattr(request, "selected_text", "") or "").strip()
    if not text:
        return None
    source_id = str(getattr(request, "active_file_id", "") or "").strip()
    if not source_id:
        selected_ids = [
            str(item).strip()
            for item in getattr(request, "selected_file_ids", None) or []
            if str(item).strip()
        ]
        source_id = selected_ids[0] if len(selected_ids) == 1 else ""
    if not source_id:
        return None
    source_name = str(getattr(request, "active_file_name", "") or "").strip()
    return EvidenceElement(
        evidence_id=f"selected-text:{source_id}",
        source_id=source_id,
        source_name=source_name,
        modality="text",
        text=text,
        source_backrefs=[f"{source_id}#source"],
        evidence_level="source",
        metadata={"route": route},
    ).as_dict()


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return canonicalize_and_dedupe_evidence(items)[0]


def _reranked_with_remaining_candidates(
    reranked: list[dict[str, Any]] | None,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if reranked is None:
        return candidates
    reranked_ids = {identity_of(item).key for item in reranked}
    return [
        *reranked,
        *(item for item in candidates if identity_of(item).key not in reranked_ids),
    ]


def _string_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        values: list[Any] = list(value.values())
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    elif value is None:
        return []
    else:
        values = [value]
    return list(
        dict.fromkeys(str(item).strip() for item in values if str(item).strip())
    )


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


_MODALITY_TERMS = {
    "page_image": {"chart", "diagram", "figure", "image", "plot", "slide", "visual"},
    "figure": {"chart", "diagram", "figure", "image", "plot", "visual"},
    "table": {"column", "row", "table"},
    "formula": {"equation", "formula", "latex", "math"},
    "slide": {"deck", "presentation", "ppt", "pptx", "slide"},
}


def _rank_route_items(
    items: list[dict[str, Any]], request: Any, route: str
) -> list[dict[str, Any]]:
    query_tokens = _tokens(
        f"{getattr(request, 'prompt', '')} {getattr(request, 'selected_text', '')}"
    )
    if not query_tokens:
        return items
    ranked = [
        (_route_item_score(item, request, query_tokens, route), index, item)
        for index, item in enumerate(items)
    ]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item for _, _, item in ranked]


def _route_item_score(
    item: dict[str, Any],
    request: Any,
    query_tokens: set[str],
    route: str,
) -> int:
    score = len(query_tokens & _item_tokens(item))
    modality = str(item.get("modality") or "").strip()
    score += _visual_retriever_score(item)
    score += 3 * len(query_tokens & _metadata_tokens(item))
    if query_tokens & _MODALITY_TERMS.get(modality, set()):
        score += 8
    if route == "doc_page_image" and modality == "page_image":
        score += 2
    if route == "doc_element" and modality not in {"", "page_image", "text"}:
        score += 2
    if route == "doc_element":
        score += _element_retriever_score(item)

    active_file_id = str(getattr(request, "active_file_id", "") or "").strip()
    source_id = str(item.get("source_id") or "").strip()
    if active_file_id and source_id == active_file_id:
        score += 6
    elif source_id in _selected_file_ids(request):
        score += 3

    page_number = getattr(request, "page_number", None)
    if page_number is not None and str(item.get("page_label") or "") == str(
        page_number
    ):
        score += 4
    return score


def _selected_file_ids(request: Any) -> set[str]:
    return {
        str(item).strip()
        for item in getattr(request, "selected_file_ids", None) or []
        if str(item).strip()
    }


def _item_tokens(item: dict[str, Any]) -> set[str]:
    return _tokens(
        " ".join(
            str(item.get(key) or "")
            for key in (
                "caption",
                "element_id",
                "modality",
                "ocr_text",
                "source_name",
                "text",
                "vlm_text",
            )
        )
    )


def _metadata_tokens(item: dict[str, Any]) -> set[str]:
    metadata = dict(item.get("metadata") or {})
    values: list[Any] = [
        metadata.get("late_interaction_tokens"),
        metadata.get("visual_retriever"),
    ]
    return _tokens(
        " ".join(
            str(part)
            for value in values
            for part in (value if isinstance(value, list) else [value])
        )
    )


def _visual_retriever_score(item: dict[str, Any]) -> int:
    metadata = dict(item.get("metadata") or {})
    return int(float(metadata.get("visual_retriever_score") or 0.0) * 100)


def _element_retriever_score(item: dict[str, Any]) -> int:
    metadata = dict(item.get("metadata") or {})
    return int(float(metadata.get("element_retriever_score") or 0.0) * 100)


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if len(token) > 2
    }
