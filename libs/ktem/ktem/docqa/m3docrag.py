from __future__ import annotations

import re
from collections import Counter
from typing import Any


def select_page_first_evidence(
    query: str,
    items: list[dict[str, Any]],
    *,
    max_pages: int = 3,
    max_unpaged_items: int = 2,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    page_scores = _page_scores(query, items)
    selected_pages = [
        page
        for page, _ in sorted(
            page_scores.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        )[:max_pages]
    ]
    trace = _trace(
        items,
        selected_pages,
        pruned_item_count=0,
    )
    trace["candidate_preservation"] = "all"
    trace["ranked_unpaged_evidence_ids"] = [
        str(item.get("evidence_id") or "")
        for item in _unpaged_items(query, items, max_unpaged_items)
        if str(item.get("evidence_id") or "")
    ]
    return items, trace


def _trace(
    selected: list[dict[str, Any]],
    selected_pages: list[tuple[str, str]],
    *,
    pruned_item_count: int,
) -> dict[str, Any]:
    return {
        "selected_pages": [
            {"source_id": source_id, "page_label": page_label}
            for source_id, page_label in selected_pages
        ],
        "modality_counts": dict(Counter(item["modality"] for item in selected)),
        "pruned_item_count": pruned_item_count,
    }


def _page_scores(
    query: str, items: list[dict[str, Any]]
) -> dict[tuple[str, str], float]:
    query_tokens = _tokens(query)
    item_scores: dict[tuple[str, str], list[float]] = {}
    for item in items:
        page = _page_key(item)
        if not all(page):
            continue
        score = float(len(query_tokens & _item_tokens(item)))
        score += _hybrid_fusion_score(item)
        if item.get("modality") == "page_image":
            score += 2
        if item.get("modality") not in {"page_image", "text"}:
            score += 2
        item_scores.setdefault(page, []).append(score)
    return {page: _aggregate_page_score(scores) for page, scores in item_scores.items()}


def _aggregate_page_score(scores: list[float]) -> float:
    ranked = sorted(scores, reverse=True)
    top = ranked[:3]
    return ranked[0] + 0.25 * sum(top) / len(top)


def _page_items(
    items: list[dict[str, Any]],
    page: tuple[str, str],
) -> list[dict[str, Any]]:
    grouped = [item for item in items if _page_key(item) == page]
    return sorted(grouped, key=_modality_order)


def _unpaged_items(
    query: str,
    items: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    query_tokens = _tokens(query)
    ranked = [
        (_unpaged_item_score(query_tokens, item), index, item)
        for index, item in enumerate(items)
        if not all(_page_key(item))
    ]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item for _, _, item in ranked[:limit]]


def _unpaged_item_score(query_tokens: set[str], item: dict[str, Any]) -> int:
    score = len(query_tokens & _item_tokens(item))
    score += _hybrid_fusion_score(item)
    if item.get("modality") == "graph":
        score += 2
    return score


def _page_key(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("source_id") or "").strip(),
        str(item.get("page_label") or "").strip(),
    )


def _modality_order(item: dict[str, Any]) -> tuple[int, str]:
    order = {"text": 0, "page_image": 1}
    fusion_score = _hybrid_fusion_sort_score(item)
    if fusion_score:
        return (-fusion_score, str(item.get("evidence_id") or ""))
    modality = str(item.get("modality") or "")
    return (order.get(modality, 2), str(item.get("evidence_id") or ""))


def _hybrid_fusion_sort_score(item: dict[str, Any]) -> int:
    metadata = dict(item.get("metadata") or {})
    components = metadata.get("hybrid_fusion_components")
    if not isinstance(components, dict):
        return 0
    return _hybrid_fusion_score(item)


def _hybrid_fusion_score(item: dict[str, Any]) -> int:
    metadata = dict(item.get("metadata") or {})
    return int(float(metadata.get("hybrid_fusion_score") or 0.0) * 1000)


def _item_tokens(item: dict[str, Any]) -> set[str]:
    metadata = dict(item.get("metadata") or {})
    return _tokens(
        " ".join(
            [
                str(item.get("caption") or ""),
                str(item.get("element_id") or ""),
                str(item.get("modality") or ""),
                str(item.get("ocr_text") or ""),
                str(item.get("source_name") or ""),
                str(item.get("text") or ""),
                str(item.get("vlm_text") or ""),
                " ".join(str(value) for value in metadata.values()),
            ]
        )
    )


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if len(token) > 2
    }
