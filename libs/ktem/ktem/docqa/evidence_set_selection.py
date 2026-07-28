from __future__ import annotations

import math
import re
from typing import Any

from .evidence_identity import evidence_aliases, identity_of
from .evidence_set_objective import marginal_set_gain
from .evidence_structure import structure_coverage_context
from .query_planning import (
    QueryPlan,
    bind_evidence_slots,
    retrieval_budget,
    slot_coverage,
)
from .required_slot_selection import required_slot_shortlist
from .required_slot_selection import slot_score as _slot_score

MMR_LAMBDA = 0.7
RERANK_CANDIDATE_LIMIT = 30

_TOKEN_RE = re.compile(r"[\w.%$€£¥-]+", re.UNICODE)
_PHRASE_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
_QUOTED_ANCHOR_RE = re.compile(r"""["“]([^"”]{2,})["”]""")
_DATE_ANCHOR_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},?\s+(?:19|20)\d{2}\b",
    re.IGNORECASE,
)
_NUMBERED_ANCHOR_RE = re.compile(
    r"\b(?:episode|chapter|section|season)\s+\d+\b",
    re.IGNORECASE,
)
_PROPER_PHRASE_RE = re.compile(
    r"\b[A-Z][\w'’-]*(?:\s+(?:(?:of|the|and|in|on|for)\s+)?" r"[A-Z][\w'’-]*)+\b"
)
_PHRASE_STOPWORDS = {
    "a",
    "an",
    "and",
    "did",
    "do",
    "does",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "was",
    "were",
    "what",
    "when",
    "which",
    "who",
}
_ANCHOR_GENERIC_TOKENS = _PHRASE_STOPWORDS | {
    "air",
    "answer",
    "as",
    "be",
    "built",
    "die",
    "died",
    "dies",
    "episode",
    "open",
    "opened",
    "season",
    "sing",
    "sings",
    "start",
    "version",
}


def select_evidence_for_plan(
    query: str,
    items: list[dict[str, Any]],
    plan: QueryPlan,
    *,
    mmr_lambda: float = MMR_LAMBDA,
) -> tuple[list[dict[str, Any]], dict[str, Any], QueryPlan]:
    candidates, restored_required, budget = _selection_context(items, plan)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    _seed_unplanned_selection(query, candidates, plan, selected, selected_ids)
    _select_required_slot_evidence(
        query,
        candidates,
        plan,
        selected,
        selected_ids,
        max_pages=budget["max_pages"],
    )

    page_modality_count = 0
    if plan.question_type == "visual":
        page_modality_count = _expand_selected_pages(
            candidates,
            selected,
            selected_ids,
            max_items=budget["max_items"],
        )

    (
        structure_coverage,
        mixed_structure_coverage,
        structure_coverage_scope,
    ) = structure_coverage_context(candidates)
    structure_expansion_enabled = any(
        item.get("continuation_id")
        or item.get("parent_element_id")
        or item.get("neighbor_element_ids")
        for item in candidates
    )
    continuation_count = 0
    if structure_expansion_enabled:
        continuation_count = _expand_structure(
            candidates,
            selected,
            selected_ids,
            max_items=budget["max_items"],
            max_pages=budget["max_pages"],
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
    )
    bound = bind_evidence_slots(plan, selected)
    trace = _selection_trace(
        candidates,
        selected,
        bound,
        budget,
        structure_coverage=structure_coverage,
        structure_expansion_enabled=structure_expansion_enabled,
        continuation_count=continuation_count,
        page_modality_count=page_modality_count,
        mmr_lambda=mmr_lambda,
        required_slot_candidates_restored=restored_required,
        mixed_structure_coverage=mixed_structure_coverage,
        structure_coverage_scope=structure_coverage_scope,
    )
    return selected, trace, bound


def _selection_context(
    items: list[dict[str, Any]],
    plan: QueryPlan,
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    candidates, restored_required = required_slot_shortlist(
        items,
        plan,
        candidate_limit=RERANK_CANDIDATE_LIMIT,
    )
    return candidates, restored_required, retrieval_budget(plan)


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
) -> None:
    used_required_locators: set[tuple[str, str]] = set()
    for slot in plan.evidence_slots:
        ranked = sorted(
            candidates,
            key=lambda item: (
                -_slot_score(plan, slot, item),
                -_relevance(query, item),
                _identity(item),
            ),
        )
        match = next(
            (
                item
                for item in ranked
                if _slot_score(plan, slot, item) > 0
                and _identity(item) not in selected_ids
                and _page_allowed(item, selected, max_pages)
                and (
                    not plan.constraints.get("requires_distinct_source_pages")
                    or slot.role != "support"
                    or (all(_page(item)) and _page(item) not in used_required_locators)
                )
            ),
            None,
        )
        if match is not None:
            _append_selected(match, selected, selected_ids)
            if (
                plan.constraints.get("requires_distinct_source_pages")
                and slot.role == "support"
                and all(_page(match))
            ):
                used_required_locators.add(_page(match))


def _selection_trace(
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    bound: QueryPlan,
    budget: dict[str, int],
    *,
    structure_coverage: float,
    structure_expansion_enabled: bool,
    continuation_count: int,
    page_modality_count: int,
    mmr_lambda: float,
    required_slot_candidates_restored: int,
    mixed_structure_coverage: float,
    structure_coverage_scope: str,
) -> dict[str, Any]:
    pages = _pages(selected)
    return {
        "strategy": "marginal_evidence_set_selection_v3",
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "max_items": budget["max_items"],
        "max_pages": budget["max_pages"],
        "unique_pages": len(pages),
        "selected_pages": [
            {"source_id": source, "page_label": page} for source, page in pages
        ],
        "slot_coverage": slot_coverage(bound),
        "missing_required_slot_count": sum(
            slot.required_for_retrieval and slot.status != "filled"
            for slot in bound.evidence_slots
        ),
        "continuation_expansion_count": continuation_count,
        "page_modality_expansion_count": page_modality_count,
        "structure_expansion_enabled": structure_expansion_enabled,
        "mmr_lambda": mmr_lambda,
        "structure_metadata_coverage": structure_coverage,
        "mixed_candidate_structure_metadata_coverage": mixed_structure_coverage,
        "structure_coverage_scope": structure_coverage_scope,
        "required_slot_candidates_restored": required_slot_candidates_restored,
    }


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
                    + marginal_set_gain(item, selected, plan)
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
    score = _first_float(
        metadata.get("learned_score"),
        metadata.get("reranking_score"),
        metadata.get("reranker_score"),
        metadata.get("hybrid_fusion_score"),
        metadata.get("visual_retriever_score"),
        metadata.get("element_retriever_score"),
        item.get("score"),
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
    return (
        lexical
        + metadata_match
        + score
        + 1.75 * _anchor_coverage(query, _item_text(item))
        + 0.5 * _phrase_bigram_coverage(query, _item_text(item))
    )


def _anchor_coverage(query: str, item_text: str) -> float:
    anchors = _query_anchors(query)
    if not anchors:
        return 0.0
    normalized_text = _normalized_phrase(item_text)
    return sum(anchor in normalized_text for anchor in anchors) / len(anchors)


def _query_anchors(query: str) -> tuple[str, ...]:
    raw_anchors = [
        *(_QUOTED_ANCHOR_RE.findall(query)),
        *(_DATE_ANCHOR_RE.findall(query)),
        *(_NUMBERED_ANCHOR_RE.findall(query)),
        *(_PROPER_PHRASE_RE.findall(query)),
        *_content_bigram_anchors(query),
    ]
    anchors: list[str] = []
    for value in raw_anchors:
        normalized = _normalized_phrase(value)
        tokens = normalized.split()
        if (
            len(tokens) >= 2
            and any(token not in _PHRASE_STOPWORDS for token in tokens)
            and normalized not in anchors
        ):
            anchors.append(normalized)
    return tuple(anchors)


def _content_bigram_anchors(query: str) -> list[str]:
    tokens = [token.lower() for token in _PHRASE_TOKEN_RE.findall(str(query or ""))]
    return list(
        dict.fromkeys(
            f"{left} {right}"
            for left, right in zip(tokens, tokens[1:])
            if len(left) > 1
            and len(right) > 1
            and left not in _ANCHOR_GENERIC_TOKENS
            and right not in _ANCHOR_GENERIC_TOKENS
        )
    )


def _phrase_bigram_coverage(query: str, item_text: str) -> float:
    query_tokens = [
        token.lower() for token in _PHRASE_TOKEN_RE.findall(str(query or ""))
    ]
    bigrams = list(
        dict.fromkeys(
            f"{left} {right}"
            for left, right in zip(query_tokens, query_tokens[1:])
            if left not in _PHRASE_STOPWORDS or right not in _PHRASE_STOPWORDS
        )
    )
    if not bigrams:
        return 0.0
    normalized_text = _normalized_phrase(item_text)
    return sum(bigram in normalized_text for bigram in bigrams) / len(bigrams)


def _normalized_phrase(text: str) -> str:
    return " ".join(
        token.lower() for token in _PHRASE_TOKEN_RE.findall(str(text or ""))
    )


def _similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    embedding_similarity = _embedding_cosine(left, right)
    if embedding_similarity is not None:
        return embedding_similarity
    a = _tokens(_item_text(left))
    b = _tokens(_item_text(right))
    return len(a & b) / len(a | b) if a and b else 0.0


def _embedding_cosine(left: dict[str, Any], right: dict[str, Any]) -> float | None:
    a = _embedding(left)
    b = _embedding(right)
    if not a or not b or len(a) != len(b):
        return None
    denominator = math.sqrt(sum(value * value for value in a)) * math.sqrt(
        sum(value * value for value in b)
    )
    if denominator == 0:
        return None
    return sum(x * y for x, y in zip(a, b)) / denominator


def _embedding(item: dict[str, Any]) -> list[float]:
    metadata = dict(item.get("metadata") or {})
    value = metadata.get("semantic_embedding") or metadata.get("embedding") or []
    if not isinstance(value, (list, tuple)):
        return []
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return []


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


def _item_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "vlm_text", "caption")
    )


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(str(text or ""))}


def _first_float(*values: Any) -> float:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _string_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        values: list[Any] = list(value.values())
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    elif value is None:
        return []
    else:
        values = [value]
    return [str(item).strip() for item in values if str(item).strip()]
