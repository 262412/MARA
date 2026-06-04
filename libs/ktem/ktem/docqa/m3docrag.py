from __future__ import annotations

import re
from collections import Counter
from typing import Any


def select_page_first_evidence(
    query: str,
    items: list[dict[str, Any]],
    *,
    max_pages: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    page_scores = _page_scores(query, items)
    selected_pages = [
        page
        for page, _ in sorted(
            page_scores.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        )[:max_pages]
    ]
    selected = [item for page in selected_pages for item in _page_items(items, page)]
    selected.extend(item for item in items if _page_key(item) not in selected_pages)
    return selected, {
        "selected_pages": [
            {"source_id": source_id, "page_label": page_label}
            for source_id, page_label in selected_pages
        ],
        "modality_counts": dict(Counter(item["modality"] for item in selected)),
    }


def _page_scores(query: str, items: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
    query_tokens = _tokens(query)
    scores: dict[tuple[str, str], int] = {}
    for item in items:
        page = _page_key(item)
        if not all(page):
            continue
        score = len(query_tokens & _item_tokens(item))
        if item.get("modality") == "page_image":
            score += 2
        if item.get("modality") not in {"page_image", "text"}:
            score += 2
        scores[page] = scores.get(page, 0) + score
    return scores


def _page_items(
    items: list[dict[str, Any]],
    page: tuple[str, str],
) -> list[dict[str, Any]]:
    grouped = [item for item in items if _page_key(item) == page]
    return sorted(grouped, key=_modality_order)


def _page_key(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("source_id") or "").strip(),
        str(item.get("page_label") or "").strip(),
    )


def _modality_order(item: dict[str, Any]) -> tuple[int, str]:
    order = {"text": 0, "page_image": 1}
    modality = str(item.get("modality") or "")
    return (order.get(modality, 2), str(item.get("evidence_id") or ""))


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
