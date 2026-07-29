from __future__ import annotations

import re
from typing import Any

from .qasper_boolean_scope import scope_valid_support_items
from .verified_claim_citations import verified_claim_support_groups


def minimum_verified_claim_support_items(
    prediction: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    span: str,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for group in verified_claim_support_groups(prediction, candidates):
        scoped = _scope_valid_group(prediction, group, span=span)
        if scoped:
            selected.append(_best_item(prediction, scoped, span=span))
    return selected


def _scope_valid_group(
    prediction: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    span: str,
) -> list[dict[str, Any]]:
    if str(prediction.get("answer_type") or "").strip().lower() != "boolean":
        return items
    return scope_valid_support_items(
        str(prediction.get("question") or ""),
        span,
        items,
    )


def _best_item(
    prediction: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    span: str,
) -> dict[str, Any]:
    query_tokens = _tokens(f"{prediction.get('question') or ''} {span}")
    return max(
        items,
        key=lambda item: (
            len(query_tokens & _tokens(_item_text(item))),
            -len(_item_text(item)),
        ),
    )


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if item.get(field)
    )
