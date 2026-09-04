from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_locators import (
    normalized_page_aliases,
    normalized_source_page_locators,
)
from ktem.docqa.source_identity_crosswalk import SourceIdentityResolver


def source_join_metrics(
    prediction: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, float | None]:
    resolver = SourceIdentityResolver(
        prediction.get("source_identity_crosswalk")
        or dict(prediction.get("evidence_metadata") or {}).get(
            "source_identity_crosswalk"
        )
        or []
    )
    gold_records = _records(prediction.get("gold_evidence"))
    gold_sources = _gold_sources(prediction, gold_records)
    resolved_sources = {source for source in gold_sources if resolver.resolve(source)}
    source_join_rate = (
        len(resolved_sources) / len(gold_sources) if gold_sources else None
    )
    page_alias_resolution_rate = _gold_page_alias_resolution_rate(gold_records)
    crosswalk_rate = _gold_source_page_crosswalk_rate(
        gold_records,
        resolver,
    )
    retrieval_coverage = _page_join_rate(
        candidates,
        gold_records,
        resolver,
    )
    return {
        "gold_source_alias_resolution_rate": source_join_rate,
        "gold_page_alias_resolution_rate": page_alias_resolution_rate,
        "gold_source_page_crosswalk_rate": crosswalk_rate,
        "retrieved_gold_source_page_coverage": retrieval_coverage,
        "gold_runtime_source_join_rate": source_join_rate,
        "unresolved_gold_source_count": float(
            len(gold_sources) - len(resolved_sources)
        ),
        "ambiguous_source_alias_count": float(resolver.ambiguous_alias_count),
        "gold_runtime_source_page_join_rate": retrieval_coverage,
        "gold_source_schema_valid": _schema_valid(prediction, gold_sources),
        "gold_source_id_count": float(len(gold_sources)),
        "gold_evidence_text_support_recall": _text_support_recall(
            prediction,
            gold_records,
            candidates,
        ),
    }


def _gold_page_alias_resolution_rate(
    gold_records: list[dict[str, Any]],
) -> float | None:
    records = [
        item
        for item in gold_records
        if str(item.get("page_label") or item.get("page") or "").strip()
    ]
    if not records:
        return None
    return sum(bool(normalized_page_aliases(item)) for item in records) / len(records)


def _gold_source_page_crosswalk_rate(
    gold_records: list[dict[str, Any]],
    resolver: SourceIdentityResolver,
) -> float | None:
    records = [
        item
        for item in gold_records
        if str(item.get("page_label") or item.get("page") or "").strip()
    ]
    if not records:
        return None
    resolved = 0
    for item in records:
        source = item.get("source_id") or item.get("document_id") or ""
        if resolver.resolve(source) and normalized_page_aliases(item):
            resolved += 1
    return resolved / len(records)


def _gold_sources(
    prediction: dict[str, Any],
    gold_records: list[dict[str, Any]],
) -> set[str]:
    sources = {
        str(value).strip()
        for value in prediction.get("gold_source_ids") or []
        if str(value).strip()
    }
    sources.update(
        str(item.get("source_id") or item.get("document_id") or "").strip()
        for item in gold_records
        if str(item.get("source_id") or item.get("document_id") or "").strip()
    )
    if not sources:
        sources.update(
            str(value).split("#", 1)[0].strip()
            for value in prediction.get("gold_sources") or []
            if str(value).strip()
        )
    return sources


def _page_join_rate(
    candidates: list[dict[str, Any]],
    gold_records: list[dict[str, Any]],
    resolver: SourceIdentityResolver,
) -> float | None:
    candidate_pairs = set().union(
        *(normalized_source_page_locators(item) for item in candidates)
    )
    canonical_candidates = {
        (resolver.canonical_or_original(source), page)
        for source, page in candidate_pairs
    }
    gold_pairs = {
        (
            resolver.canonical_or_original(
                item.get("source_id") or item.get("document_id") or ""
            ),
            str(item.get("page_label") or item.get("page") or "").strip(),
        )
        for item in gold_records
        if str(item.get("page_label") or item.get("page") or "").strip()
    }
    if not gold_pairs:
        return None
    return sum(pair in canonical_candidates for pair in gold_pairs) / len(gold_pairs)


def _text_support_recall(
    prediction: dict[str, Any],
    gold_records: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> float | None:
    gold_texts = [
        str(value).strip()
        for value in prediction.get("gold_evidence_texts") or []
        if str(value).strip()
    ] or [
        str(item.get("span") or item.get("text") or "").strip()
        for item in gold_records
        if str(item.get("span") or item.get("text") or "").strip()
    ]
    if not gold_texts:
        return None
    candidate_text = "\n".join(
        str(item.get("text") or item.get("content") or "").strip()
        for item in candidates
    ).casefold()
    return sum(text.casefold() in candidate_text for text in gold_texts) / len(
        gold_texts
    )


def _schema_valid(
    prediction: dict[str, Any],
    gold_sources: set[str],
) -> float | None:
    expected = {
        str(value).strip()
        for value in prediction.get("document_ids") or [prediction.get("document_id")]
        if str(value or "").strip()
    }
    return float(gold_sources <= expected) if gold_sources and expected else None


def _records(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, dict)]
