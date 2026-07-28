from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from ktem.docqa.evidence_identity import exact_evidence_aliases, identity_of

from .page_alignment import evidence_item_text, evidence_text_supports_gold_locator

_SOURCE_FIELDS = (
    "source_id",
    "document_id",
    "doc_id",
    "file_id",
    "source_name",
    "file_name",
)


def evidence_identity_keys(item: dict[str, Any]) -> set[str]:
    identity = identity_of(item)
    keys = {f"identity:{identity.key}"}
    for value in exact_evidence_aliases(item):
        normalized = _normalized_identifier(value)
        if normalized:
            keys.add(f"id:{normalized}")

    aliases = source_aliases(item)
    page = _page_label(item)
    text_hash = _text_hash(evidence_item_text(item))
    element = _normalized_identifier(identity.local_id)
    for alias in aliases:
        if element:
            keys.add(f"source_element:{alias}:{element}")
        if page and text_hash:
            keys.add(f"source_page_text:{alias}:{page}:{text_hash}")
    return keys


def reranker_lineage(
    candidate_pool: list[dict[str, Any]],
    reranked_items: list[dict[str, Any]],
) -> tuple[float, int]:
    if not reranked_items:
        return 1.0, 0
    pool_keys = set().union(*(evidence_identity_keys(item) for item in candidate_pool))
    violations = sum(
        not bool(evidence_identity_keys(item) & pool_keys) for item in reranked_items
    )
    return (len(reranked_items) - violations) / len(reranked_items), violations


def gold_evidence_support_recall(
    items: list[dict[str, Any]] | None,
    gold_records: list[dict[str, Any]],
) -> float | None:
    applicable_gold = [
        record
        for record in gold_records
        if any(
            str(record.get(field) or "").strip()
            for field in ("span", "text", "quote", "evidence")
        )
    ]
    if items is None or not applicable_gold:
        return None
    supported = sum(
        any(_item_supports_gold(item, gold) for item in items)
        for gold in applicable_gold
    )
    return supported / len(applicable_gold)


def source_aliases(item: dict[str, Any]) -> set[str]:
    values: list[Any] = [item.get(field) for field in _SOURCE_FIELDS]
    values.extend(_as_values(item.get("source_aliases")))
    values.extend(_as_values(item.get("source_backrefs")))
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        values.extend(metadata.get(field) for field in _SOURCE_FIELDS)
        values.extend(_as_values(metadata.get("source_aliases")))
    aliases: set[str] = set()
    for value in values:
        aliases.update(_source_value_aliases(value))
    return aliases


def _as_values(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    return list(value) if isinstance(value, (list, tuple, set)) else [value]


def _item_supports_gold(item: dict[str, Any], gold: dict[str, Any]) -> bool:
    gold_sources = source_aliases(gold)
    if gold_sources and not (source_aliases(item) & gold_sources):
        return False
    return evidence_text_supports_gold_locator(gold, evidence_item_text(item))


def _source_value_aliases(value: Any) -> set[str]:
    text = str(value or "").strip().split("#", 1)[0]
    if not text:
        return set()
    filename = Path(text).name
    stem = filename.rsplit(".", 1)[0]
    return {
        alias
        for raw in (text, filename, stem)
        if (alias := _normalized_identifier(raw))
    }


def _page_label(item: dict[str, Any]) -> str:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    for field in (
        "page_label",
        "source_page_label",
        "dataset_page",
        "parser_page_index",
        "page",
        "page_index",
    ):
        value = item.get(field, nested.get(field))
        if str(value or "").strip():
            return str(value).strip().lower()
    return ""


def _normalized_identifier(value: Any) -> str:
    return re.sub(r"[^a-z0-9._:-]+", "-", str(value or "").strip().lower()).strip("-")


def _text_hash(text: str) -> str:
    normalized = " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
