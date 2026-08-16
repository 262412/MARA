from __future__ import annotations

from typing import Any

from .evidence_identity import evidence_aliases, identity_of
from .evidence_selection_similarity import evidence_item_text as _item_text
from .evidence_selection_similarity import selection_similarity as _similarity
from .evidence_selection_similarity import selection_tokens as _tokens
from .evidence_selection_trace import build_selection_trace
from .evidence_set_objective import marginal_set_gain
from .evidence_structure import structure_coverage_context
from .execution_slot_lineage import (
    is_atomic_operand_candidate,
    linked_dimension_candidate,
)
from .query_evidence_binding import bind_evidence_slots
from .query_planning import QueryPlan, retrieval_budget
from .required_slot_selection import (
    required_slot_candidate_limit,
    required_slot_context_quota,
    required_slot_shortlist,
    slot_requires_selection,
)
from .required_slot_selection import slot_score as _slot_score
from .selection_assessment_snapshot import SelectionAssessmentSnapshot
from .selection_query_anchors import anchor_coverage, phrase_bigram_coverage
from .selection_score_normalization import (
    normalized_selection_scores,
    without_selection_annotations,
)
from .selection_values import first_float as _first_float
from .selection_values import string_values as _string_values

MMR_LAMBDA = 0.7
RERANK_CANDIDATE_LIMIT = 30


def select_evidence_for_plan(
    query: str,
    items: list[dict[str, Any]],
    plan: QueryPlan,
    *,
    mmr_lambda: float = MMR_LAMBDA,
    assessments: SelectionAssessmentSnapshot | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], QueryPlan]:
    assessments = assessments or SelectionAssessmentSnapshot.build(plan, items)
    assessments = assessments.expanded(plan, items)
    candidates, restored_required, budget = _selection_context(
        items,
        plan,
        assessments=assessments,
    )
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    _select_plan_requirements(
        query,
        candidates,
        plan,
        selected,
        selected_ids,
        max_pages=budget["max_pages"],
        assessments=assessments,
    )
    context = _complete_context_selection(
        query,
        candidates,
        plan,
        selected,
        selected_ids,
        budget=budget,
        mmr_lambda=mmr_lambda,
        assessments=assessments,
    )
    bound = bind_evidence_slots(plan, selected, assessments=assessments)
    trace = build_selection_trace(
        candidates,
        selected,
        bound,
        budget,
        {
            **context,
            "required_slot_candidates_restored": restored_required,
        },
        assessments=assessments,
    )
    return [without_selection_annotations(item) for item in selected], trace, bound


def _select_plan_requirements(
    query: str,
    candidates: list[dict[str, Any]],
    plan: QueryPlan,
    selected: list[dict[str, Any]],
    selected_ids: set[str],
    *,
    max_pages: int,
    assessments: SelectionAssessmentSnapshot,
) -> None:
    _seed_unplanned_selection(query, candidates, plan, selected, selected_ids)
    _select_required_slot_evidence(
        query,
        candidates,
        plan,
        selected,
        selected_ids,
        max_pages=max_pages,
        phase="execution_operand",
        assessments=assessments,
    )
    _select_execution_parents(
        query,
        candidates,
        plan,
        selected,
        selected_ids,
        max_pages=max_pages,
        assessments=assessments,
    )
    _select_execution_dimensions(
        candidates,
        plan,
        selected,
        selected_ids,
        max_pages=max_pages,
        assessments=assessments,
    )
    for phase in ("dimension", "factual"):
        _select_required_slot_evidence(
            query,
            candidates,
            plan,
            selected,
            selected_ids,
            max_pages=max_pages,
            phase=phase,
            assessments=assessments,
        )


def _complete_context_selection(
    query: str,
    candidates: list[dict[str, Any]],
    plan: QueryPlan,
    selected: list[dict[str, Any]],
    selected_ids: set[str],
    *,
    budget: dict[str, int],
    mmr_lambda: float,
    assessments: SelectionAssessmentSnapshot,
) -> dict[str, Any]:
    page_modality_count = 0
    if plan.constraints.get("requires_visual") or plan.question_type == "visual":
        page_modality_count = _expand_selected_pages(
            candidates,
            selected,
            selected_ids,
            max_items=budget["max_items"],
        )
    coverage, mixed_coverage, coverage_scope = structure_coverage_context(candidates)
    expansion_enabled = any(
        item.get("continuation_id")
        or item.get("parent_element_id")
        or item.get("neighbor_element_ids")
        for item in candidates
    )
    continuation_count = (
        _expand_structure(
            candidates,
            selected,
            selected_ids,
            max_items=budget["max_items"],
            max_pages=budget["max_pages"],
        )
        if expansion_enabled
        else 0
    )
    _fill_with_mmr(
        query,
        candidates,
        plan,
        selected,
        selected_ids,
        max_items=budget["max_items"],
        max_pages=budget["max_pages"],
        mmr_lambda=mmr_lambda,
        assessments=assessments,
    )
    return {
        "continuation_expansion_count": continuation_count,
        "page_modality_expansion_count": page_modality_count,
        "structure_expansion_enabled": expansion_enabled,
        "mmr_lambda": mmr_lambda,
        "structure_metadata_coverage": coverage,
        "mixed_candidate_structure_metadata_coverage": mixed_coverage,
        "structure_coverage_scope": coverage_scope,
    }


def _select_execution_parents(
    query: str,
    candidates: list[dict[str, Any]],
    plan: QueryPlan,
    selected: list[dict[str, Any]],
    selected_ids: set[str],
    *,
    max_pages: int,
    assessments: SelectionAssessmentSnapshot,
) -> None:
    for slot in plan.evidence_slots:
        if not (
            slot.required_for_retrieval
            and slot.required_for_execution
            and slot.role == "operand"
        ):
            continue
        parent = min(
            (
                item
                for item in candidates
                if not is_atomic_operand_candidate(item)
                and _slot_score(plan, slot, item, assessments=assessments) > 0
                and _identity(item) not in selected_ids
                and _page_allowed(item, selected, max_pages)
            ),
            key=lambda item: (
                -_slot_score(plan, slot, item, assessments=assessments),
                -_relevance(query, item),
                _identity(item),
            ),
            default=None,
        )
        if parent is not None:
            _append_selected(parent, selected, selected_ids)


def _select_execution_dimensions(
    candidates: list[dict[str, Any]],
    plan: QueryPlan,
    selected: list[dict[str, Any]],
    selected_ids: set[str],
    *,
    max_pages: int,
    assessments: SelectionAssessmentSnapshot,
) -> None:
    execution_slots = [
        slot
        for slot in plan.evidence_slots
        if slot.required_for_execution and slot.role == "operand"
    ]
    selected_operands = [
        item
        for item in selected
        if is_atomic_operand_candidate(item)
        and any(
            _slot_score(plan, slot, item, assessments=assessments) > 0
            for slot in execution_slots
        )
    ]
    for operand in selected_operands:
        dimension = linked_dimension_candidate(operand, candidates)
        if (
            dimension is not None
            and _identity(dimension) not in selected_ids
            and _page_allowed(dimension, selected, max_pages)
        ):
            _append_selected(dimension, selected, selected_ids)


def _selection_context(
    items: list[dict[str, Any]],
    plan: QueryPlan,
    *,
    assessments: SelectionAssessmentSnapshot,
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    candidates, restored_required = required_slot_shortlist(
        items,
        plan,
        candidate_limit=required_slot_candidate_limit(
            plan,
            base_limit=RERANK_CANDIDATE_LIMIT,
        ),
        assessments=assessments,
    )
    return (
        normalized_selection_scores(candidates, identity_of=_identity),
        restored_required,
        retrieval_budget(plan),
    )


def _seed_unplanned_selection(
    query: str,
    candidates: list[dict[str, Any]],
    plan: QueryPlan,
    selected: list[dict[str, Any]],
    selected_ids: set[str],
) -> None:
    if not candidates or plan.evidence_slots:
        return
    lead = candidates[0]
    if plan.question_type == "simple_fact":
        lead = min(
            candidates,
            key=lambda item: (-_relevance(query, item), _identity(item)),
        )
    _append_selected(lead, selected, selected_ids)


def _select_required_slot_evidence(
    query: str,
    candidates: list[dict[str, Any]],
    plan: QueryPlan,
    selected: list[dict[str, Any]],
    selected_ids: set[str],
    *,
    max_pages: int,
    phase: str,
    assessments: SelectionAssessmentSnapshot,
) -> None:
    used_required_locators: set[tuple[str, str]] = set()
    distinct_slot_ids = set(plan.constraints.get("distinct_source_page_slot_ids") or [])
    required_slots = [
        slot
        for slot in plan.evidence_slots
        if slot_requires_selection(slot) and _slot_selection_phase(slot) == phase
    ]
    required_slots.sort(
        key=lambda slot: (
            sum(
                _slot_score(plan, slot, item, assessments=assessments) > 0
                for item in candidates
            ),
            slot.slot_id,
        )
    )
    for slot in required_slots:
        ranked = sorted(
            candidates,
            key=lambda item: (
                -_slot_score(plan, slot, item, assessments=assessments),
                -_relevance(query, item),
                _identity(item),
            ),
        )
        remaining_quota = required_slot_context_quota(slot, candidates)
        for match in ranked:
            if not (
                _slot_score(plan, slot, match, assessments=assessments) > 0
                and (
                    not (slot.required_for_execution and slot.role == "operand")
                    or is_atomic_operand_candidate(match)
                )
                and _identity(match) not in selected_ids
                and (
                    (slot.required_for_execution and slot.role == "operand")
                    or _page_allowed(match, selected, max_pages)
                )
                and (
                    not plan.constraints.get("requires_distinct_source_pages")
                    or (distinct_slot_ids and slot.slot_id not in distinct_slot_ids)
                    or (
                        not distinct_slot_ids
                        and slot.role not in {"support", "operand"}
                    )
                    or (
                        all(_page(match)) and _page(match) not in used_required_locators
                    )
                )
            ):
                continue
            _append_selected(match, selected, selected_ids)
            if (
                plan.constraints.get("requires_distinct_source_pages")
                and (
                    slot.slot_id in distinct_slot_ids
                    or (not distinct_slot_ids and slot.role in {"support", "operand"})
                )
                and all(_page(match))
            ):
                used_required_locators.add(_page(match))
            remaining_quota -= 1
            if remaining_quota == 0:
                break


def _slot_selection_phase(slot: Any) -> str:
    if slot.required_for_execution and slot.role == "operand":
        return "execution_operand"
    if slot.role == "dimension":
        return "dimension"
    return "factual"


def _expand_selected_pages(
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    selected_ids: set[str],
    *,
    max_items: int,
) -> int:
    selected_pages = set(_pages(selected))
    count = 0
    for item in candidates:
        if len(selected) >= max_items:
            break
        if _identity(item) in selected_ids or _page(item) not in selected_pages:
            continue
        _append_selected(item, selected, selected_ids)
        count += 1
    return count


def _expand_structure(
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    selected_ids: set[str],
    *,
    max_items: int,
    max_pages: int,
) -> int:
    continuation_ids = {
        str(item.get("continuation_id") or "")
        for item in selected
        if str(item.get("continuation_id") or "")
    }
    parent_ids = {
        str(item.get("parent_element_id") or "")
        for item in selected
        if str(item.get("parent_element_id") or "")
    }
    count = 0
    for item in candidates:
        if len(selected) >= max_items or _identity(item) in selected_ids:
            continue
        continuation_match = bool(
            item.get("continuation_id")
            and str(item.get("continuation_id")) in continuation_ids
        )
        parent_match = bool(
            item.get("parent_element_id")
            and str(item.get("parent_element_id")) in parent_ids
        )
        neighbor_match = any(
            bool(
                evidence_aliases(item)
                & set(_string_values(selected_item.get("neighbor_element_ids")))
            )
            or bool(
                evidence_aliases(selected_item)
                & set(_string_values(item.get("neighbor_element_ids")))
            )
            for selected_item in selected
        )
        if not (continuation_match or parent_match or neighbor_match):
            continue
        if not _page_allowed(item, selected, max_pages):
            continue
        _append_selected(item, selected, selected_ids)
        count += 1
    return count


def _fill_with_mmr(
    query: str,
    candidates: list[dict[str, Any]],
    plan: QueryPlan,
    selected: list[dict[str, Any]],
    selected_ids: set[str],
    *,
    max_items: int,
    max_pages: int,
    mmr_lambda: float,
    assessments: SelectionAssessmentSnapshot,
) -> None:
    while len(selected) < max_items:
        remaining = [
            item
            for item in candidates
            if _identity(item) not in selected_ids
            and _page_allowed(item, selected, max_pages)
        ]
        if not remaining:
            return
        ranked = sorted(
            remaining,
            key=lambda item: (
                -(
                    _mmr_score(query, item, selected, mmr_lambda)
                    + marginal_set_gain(
                        item,
                        selected,
                        plan,
                        assessments=assessments,
                        hot_loop=True,
                    )
                ),
                _identity(item),
            ),
        )
        _append_selected(ranked[0], selected, selected_ids)


def _mmr_score(
    query: str,
    item: dict[str, Any],
    selected: list[dict[str, Any]],
    mmr_lambda: float,
) -> float:
    relevance = _relevance(query, item)
    redundancy = max((_similarity(item, other) for other in selected), default=0.0)
    cost = min(1.0, len(_tokens(_item_text(item))) / 500)
    return mmr_lambda * relevance - (1.0 - mmr_lambda) * redundancy - 0.1 * cost


def _relevance(query: str, item: dict[str, Any]) -> float:
    query_tokens = _tokens(query)
    item_tokens = _tokens(_item_text(item))
    lexical = (
        len(query_tokens & item_tokens) / len(query_tokens) if query_tokens else 0.0
    )
    metadata = dict(item.get("metadata") or {})
    normalized_score = item.get("_selection_relevance_score")
    score = (
        _first_float(normalized_score)
        if normalized_score is not None
        else _first_float(
            metadata.get("learned_score"),
            metadata.get("reranking_score"),
            metadata.get("reranker_score"),
            metadata.get("hybrid_fusion_score"),
            metadata.get("visual_retriever_score"),
            metadata.get("element_retriever_score"),
            item.get("score"),
        )
    )
    metadata_tokens = _tokens(
        " ".join(
            str(value)
            for key in (
                "late_interaction_tokens",
                "section_title",
                "table_title",
            )
            for value in _string_values(metadata.get(key))
        )
    )
    metadata_match = (
        len(query_tokens & metadata_tokens) / len(query_tokens) if query_tokens else 0.0
    )
    normalized_sources = set(_string_values(item.get("_selection_relevance_sources")))
    score_weight = (
        3.0
        if normalized_sources & {"learned_score", "reranking_score", "reranker_score"}
        else 1.0
    )
    return (
        lexical
        + metadata_match
        + score_weight * score
        + 1.75 * anchor_coverage(query, _item_text(item))
        + 0.5 * phrase_bigram_coverage(query, _item_text(item))
    )


def _page_allowed(
    item: dict[str, Any], selected: list[dict[str, Any]], max_pages: int
) -> bool:
    page = _page(item)
    return (
        not all(page) or page in _pages(selected) or len(_pages(selected)) < max_pages
    )


def _pages(items: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return list(dict.fromkeys(_page(item) for item in items if all(_page(item))))


def _page(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("source_id") or ""),
        str(item.get("page_label") or ""),
    )


def _append_selected(
    item: dict[str, Any],
    selected: list[dict[str, Any]],
    selected_ids: set[str],
) -> None:
    selected.append(item)
    selected_ids.add(_identity(item))


def _identity(item: dict[str, Any]) -> str:
    return identity_of(item).key
