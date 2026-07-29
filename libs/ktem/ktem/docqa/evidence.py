from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .calculation_evidence_identity import materialize_financial_cell
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
from .financial_table import parse_financial_table_cells
from .graph_evidence import graph_items
from .hybrid_fusion import fuse_hybrid_evidence
from .m3docrag import select_page_first_evidence
from .query_planning import (
    ensure_request_query_plan,
    request_planning_question,
    retrieval_budget,
)
from .required_slot_selection import (
    required_slot_candidate_limit,
    required_slot_shortlist,
)
from .source_identity_crosswalk import canonicalize_evidence_sources

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
        execution_trace = metadata.get("reranker_execution_trace")
        if isinstance(execution_trace, dict):
            execution_trace = dict(execution_trace)
            execution_trace["backend_output_count"] = int(
                execution_trace.get("backend_output_count")
                or execution_trace.get("output_count")
                or 0
            )
            execution_trace["output_count"] = len(stages.reranked)
            execution_trace["reranker_output_count"] = len(stages.reranked)
            execution_trace["reranker_artifact_record_count"] = len(stages.reranked)
            metadata["reranker_execution_trace"] = execution_trace
    ranking_metadata = dict(stages.ranking_metadata)
    if stages.reranked is not None:
        selected_identities = {identity_of(item).key for item in deduped}
        retained_count = sum(
            identity_of(item).key in selected_identities for item in stages.reranked
        )
        ranking_metadata["selection_retained_reranked_count"] = retained_count
        execution_trace = metadata.get("reranker_execution_trace")
        if isinstance(execution_trace, dict):
            execution_trace["selection_retained_reranked_count"] = retained_count
    metadata["ranking_trace"] = ranking_metadata
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
    reranker_candidate_limit = required_slot_candidate_limit(
        query_plan,
        base_limit=MAX_RERANK_CANDIDATES,
    )
    reranker_input, restored = required_slot_shortlist(
        ranked_candidates,
        query_plan,
        candidate_limit=reranker_candidate_limit,
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
    items = _materialize_execution_cells(request, items)
    return canonicalize_evidence_sources(items, crosswalk)


def _materialize_execution_cells(
    request: Any,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    plan = ensure_request_query_plan(request)
    if not any(slot.required_for_execution for slot in plan.evidence_slots):
        return items
    expanded: list[dict[str, Any]] = []
    existing = {identity_of(item).key for item in items}
    for item in items:
        expanded.append(item)
        if str(item.get("evidence_level") or "").lower() == "cell":
            continue
        for cell in parse_financial_table_cells(item):
            materialized = materialize_financial_cell(item, cell)
            identity = identity_of(materialized).key
            if identity in existing:
                continue
            existing.add(identity)
            expanded.append(materialized)
    return expanded


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
