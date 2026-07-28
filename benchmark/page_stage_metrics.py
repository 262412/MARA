from __future__ import annotations

from typing import Any


def all_gold_pages_hit(prediction: dict[str, Any]) -> float | None:
    gold_pairs = {
        (
            str(item.get("source_id") or item.get("document_id") or ""),
            str(item.get("page_label") or item.get("page") or ""),
        )
        for item in _records(prediction.get("gold_evidence"))
        if str(item.get("page_label") or item.get("page") or "")
    }
    if not gold_pairs:
        return legacy_all_gold_pages_hit(prediction)
    predicted_pairs = predicted_source_page_pairs(prediction)
    if not predicted_pairs:
        return 0.0
    return float(
        all(
            any(
                (not source or source == predicted_source)
                and page == predicted_page
                for predicted_source, predicted_page in predicted_pairs
            )
            for source, page in gold_pairs
        )
    )


def legacy_all_gold_pages_hit(prediction: dict[str, Any]) -> float | None:
    gold = {str(page) for page in prediction.get("gold_pages") or []}
    if not gold:
        return None
    predicted = {str(page) for page in prediction.get("predicted_pages") or []}
    return float(gold <= predicted)


def predicted_source_page_pairs(
    prediction: dict[str, Any],
) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    metadata = dict(prediction.get("evidence_metadata") or {})
    for key in (
        "cited_evidence",
        "verified_evidence",
        "selected_evidence",
        "candidate_evidence",
    ):
        for item in _records(metadata.get(key)):
            _add_item_locators(pairs, item)
    sources = [str(value) for value in prediction.get("predicted_sources") or []]
    pages = [str(value) for value in prediction.get("predicted_pages") or []]
    if len(sources) == len(pages):
        pairs.update(zip(sources, pages))
    for source_ref in sources:
        _add_backref_locator(pairs, source_ref)
    return pairs


def _add_item_locators(
    pairs: set[tuple[str, str]],
    item: dict[str, Any],
) -> None:
    source = str(item.get("source_id") or item.get("document_id") or "")
    page = str(item.get("page_label") or item.get("page") or "")
    if source and page:
        pairs.add((source, page))
    for source_ref in item.get("source_backrefs") or []:
        _add_backref_locator(pairs, str(source_ref or ""))


def _add_backref_locator(
    pairs: set[tuple[str, str]],
    source_ref: str,
) -> None:
    if "#page:" not in source_ref:
        return
    source, page = source_ref.split("#page:", 1)
    pairs.add((source.strip(), page.split("#", 1)[0].strip()))


def _records(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, dict)]
