from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .calculation_evidence_identity import materialize_financial_cell
from .deterministic_ranking import quantized_score
from .element_parser import parse_financial_numeric_span_records
from .evidence_identity import (
    EVIDENCE_BUNDLE_SCHEMA_VERSION,
    canonicalize_and_dedupe_evidence,
    identity_of,
)
from .evidence_item_coercion import coerce_item as _coerce_item
from .evidence_locators import merged_locator_metadata
from .evidence_planning import select_planned_evidence
from .evidence_ranking_trace import (
    actual_reranker_input,
    materialize_reranked_candidates,
)
from .evidence_schema import EvidenceBundle, EvidenceElement
from .financial_table import parse_financial_table_cells_with_context
from .graph_evidence import graph_items
from .hybrid_fusion import fuse_hybrid_evidence
from .m3docrag import select_page_first_evidence
from .query_planning import (
    ensure_request_query_plan,
    request_planning_question,
    retrieval_budget,
    score_evidence_for_slot,
)
from .required_slot_selection import (
    required_slot_candidate_limit,
    required_slot_shortlist,
)
from .selection_assessment_snapshot import SelectionAssessmentSnapshot
from .source_identity_crosswalk import canonicalize_evidence_sources
from .visual_evidence_authority import project_visual_evidence


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
    assessments: SelectionAssessmentSnapshot


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
    deduped, planning_metadata = select_planned_evidence(
        request, deduped, assessments=stages.assessments
    )
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
    ranking_metadata = dict(stages.ranking_metadata)
    execution_traces = ranking_metadata.get("reranker_execution_traces")
    if isinstance(execution_traces, list):
        metadata["reranker_execution_traces"] = execution_traces
    if stages.reranked is not None:
        selected_identities = {identity_of(item).key for item in deduped}
        retained_count = sum(
            identity_of(item).key in selected_identities for item in stages.reranked
        )
        ranking_metadata["selection_retained_reranked_count"] = retained_count
    metadata["ranking_trace"] = ranking_metadata
    metadata["reranker_aggregate_trace"] = ranking_metadata
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
    assessments = SelectionAssessmentSnapshot.build(query_plan, canonical_candidates)
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
    reranker_candidate_limit = required_slot_candidate_limit(
        query_plan,
        base_limit=80,
    )
    reranker_input, restored = required_slot_shortlist(
        ranked_candidates,
        query_plan,
        candidate_limit=reranker_candidate_limit,
        assessments=assessments,
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
        limit=required_slot_candidate_limit(query_plan, base_limit=30),
    )
    reranker_input_stage = actual_reranker_input(
        reranker_input,
        ranking_metadata,
    )
    selection_candidates = _reranked_with_remaining_candidates(
        reranked,
        reranker_input,
    )
    assessments = assessments.expanded(query_plan, selection_candidates)
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
        reranker_input=reranker_input_stage,
        reranked=reranked,
        selection_candidates=selection_candidates,
        dedupe_trace=dedupe_trace,
        ranking_metadata=ranking_metadata,
        required_slot_restored=restored,
        page_ranking_trace=page_ranking_trace,
        fusion_trace=fusion_trace,
        reranker_trace=reranker_trace,
        assessments=assessments,
    )


def _initial_evidence_items(
    route: str,
    request: Any,
    evidence_metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    base_items = [
        _coerce_item(item) for item in evidence_metadata.get("evidence") or []
    ]
    crosswalk = getattr(request, "source_identity_crosswalk", None) or []
    base_items = canonicalize_evidence_sources(base_items, crosswalk)
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
    items = project_visual_evidence(items, evidence_metadata)
    items = _materialize_execution_cells(request, items, evidence_metadata)
    return canonicalize_evidence_sources(items, crosswalk)


def _materialize_execution_cells(
    request: Any,
    items: list[dict[str, Any]],
    evidence_metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    plan = ensure_request_query_plan(request)
    slots = [
        slot
        for slot in plan.evidence_slots
        if slot.required_for_execution and slot.role == "operand"
    ]
    if not slots:
        return items
    started = time.perf_counter()
    candidate_count_before = len(items)
    expanded: list[dict[str, Any]] = []
    existing = {identity_of(item).key for item in items}
    expanded.extend(items)
    if any(slot.metric == "revolving credit capacity" for slot in slots):
        expanded.extend(_materialize_financial_narrative_spans(items, existing))
        items = list(expanded)
    cache: dict[str, tuple[Any, ...]] = {}
    cache_hits = 0
    cache_misses = 0
    parent_candidates: set[str] = set()
    materialized_tables: set[str] = set()
    per_slot_counts: dict[str, int] = {}
    for slot in slots:
        slot_matches = 0
        for item in items:
            if str(item.get("evidence_level") or "").lower() == "cell":
                continue
            if not _parent_may_contain_slot(item, slot):
                continue
            table_key = _materialization_table_key(item)
            parent_candidates.add(table_key)
            if table_key in cache:
                cells = cache[table_key]
                cache_hits += 1
            else:
                cells = parse_financial_table_cells_with_context(item, items)
                cache[table_key] = cells
                cache_misses += 1
                if cells:
                    materialized_tables.add(table_key)
            for cell in cells:
                materialized = materialize_financial_cell(item, cell)
                if score_evidence_for_slot(slot, materialized) <= 0:
                    continue
                identity = identity_of(materialized).key
                if identity not in existing:
                    existing.add(identity)
                    expanded.append(materialized)
                slot_matches += 1
        per_slot_counts[slot.slot_id] = slot_matches
    attempts = cache_hits + cache_misses
    materialized_count = len(expanded) - candidate_count_before
    evidence_metadata["materialization_trace"] = {
        "parent_table_candidate_count": len(parent_candidates),
        "materialized_table_count": len(materialized_tables),
        "materialized_cell_count": materialized_count,
        "materialization_cache_hit_rate": (cache_hits / attempts if attempts else 0.0),
        "materialized_cells_per_required_slot": (
            sum(per_slot_counts.values()) / len(slots) if slots else 0.0
        ),
        "materialized_cells_by_required_slot": per_slot_counts,
        "candidate_count_before_materialization": candidate_count_before,
        "candidate_count_after_materialization": len(expanded),
        "materialization_seconds": time.perf_counter() - started,
    }
    return expanded


def _materialize_financial_narrative_spans(
    items: list[dict[str, Any]],
    existing: set[str],
) -> list[dict[str, Any]]:
    materialized: list[dict[str, Any]] = []
    for item in items:
        metadata = {
            **dict(item.get("metadata") or {}),
            "element_id": item.get("element_id") or item.get("evidence_id"),
            "modality": item.get("modality") or item.get("element_type"),
            "evidence_level": item.get("evidence_level"),
        }
        spans = parse_financial_numeric_span_records(
            doc_id=str(item.get("evidence_id") or identity_of(item).key),
            file_id=str(item.get("source_id") or item.get("file_id") or ""),
            file_name=str(item.get("source_name") or item.get("file_name") or ""),
            page_label=str(item.get("page_label") or item.get("page") or ""),
            text="\n".join(
                str(item.get(field) or "")
                for field in ("text", "ocr_text")
                if str(item.get(field) or "").strip()
            ),
            metadata=metadata,
        )
        for span in spans:
            identity = identity_of(span).key
            if identity not in existing:
                existing.add(identity)
                materialized.append(span)
    return materialized


def _parent_may_contain_slot(item: dict[str, Any], slot: Any) -> bool:
    text = " ".join(
        str(item.get(field) or "")
        for field in ("text", "caption", "ocr_text", "table_title")
    ).lower()
    if not text.strip():
        return False
    return bool(
        item.get("table_id")
        or item.get("table_instance_id")
        or str(item.get("modality") or "").lower() == "table"
        or ("\n" in text and any(character.isdigit() for character in text))
    )


def _materialization_table_key(item: dict[str, Any]) -> str:
    return str(
        item.get("table_instance_id") or item.get("table_id") or identity_of(item).key
    )


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
    ranked.sort(
        key=lambda item: (
            -quantized_score(item[0]),
            identity_of(item[2]).key,
        )
    )
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
