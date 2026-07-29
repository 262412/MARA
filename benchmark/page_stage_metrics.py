from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_locators import normalized_source_page_locators
from ktem.docqa.source_identity_crosswalk import SourceIdentityResolver


def all_gold_pages_hit(prediction: dict[str, Any]) -> float | None:
    metadata = dict(prediction.get("evidence_metadata") or {})
    for stage in ("generation_context_evidence", "selected_evidence"):
        if stage in metadata:
            return stage_all_gold_pages_hit(prediction, stage)
    return _all_gold_pages_hit_from_pairs(
        prediction,
        predicted_source_page_pairs(prediction),
    )


def stage_all_gold_pages_hit(
    prediction: dict[str, Any],
    stage: str,
) -> float | None:
    metadata = dict(prediction.get("evidence_metadata") or {})
    pairs: set[tuple[str, str]] = set()
    resolver = _resolver(prediction)
    for item in _records(metadata.get(stage)):
        _add_item_locators(pairs, item, resolver)
    return _all_gold_pages_hit_from_pairs(prediction, pairs)


def _all_gold_pages_hit_from_pairs(
    prediction: dict[str, Any],
    predicted_pairs: set[tuple[str, str]],
) -> float | None:
    gold_pairs = {
        (_resolver(prediction).canonical_or_original(locator[0]), locator[1])
        for item in _records(prediction.get("gold_evidence"))
        for locator in normalized_source_page_locators(item)
        if locator[1]
    }
    if not gold_pairs:
        return legacy_all_gold_pages_hit(prediction)
    if not predicted_pairs:
        return 0.0
    return float(
        all(
            any(
                (not source or source == predicted_source) and page == predicted_page
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
    resolver = _resolver(prediction)
    metadata = dict(prediction.get("evidence_metadata") or {})
    for key in (
        "cited_evidence",
        "verified_evidence",
        "generation_context_evidence",
        "selected_evidence",
    ):
        for item in _records(metadata.get(key)):
            _add_item_locators(pairs, item, resolver)
    sources = [str(value) for value in prediction.get("predicted_sources") or []]
    pages = [str(value) for value in prediction.get("predicted_pages") or []]
    if len(sources) == len(pages):
        pairs.update(
            (resolver.canonical_or_original(source), page)
            for source, page in zip(sources, pages)
        )
    for source_ref in sources:
        _add_backref_locator(pairs, source_ref)
    return pairs


def _add_item_locators(
    pairs: set[tuple[str, str]],
    item: dict[str, Any],
    resolver: SourceIdentityResolver | None = None,
) -> None:
    pairs.update(
        (
            resolver.canonical_or_original(source) if resolver else source,
            page,
        )
        for source, page in normalized_source_page_locators(item)
    )


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


def _resolver(prediction: dict[str, Any]) -> SourceIdentityResolver:
    return SourceIdentityResolver(prediction.get("source_identity_crosswalk") or [])
