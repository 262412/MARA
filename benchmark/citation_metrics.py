from __future__ import annotations

from .page_alignment import (
    citation_page_label,
    citation_source_id,
    evidence_item_text,
    evidence_text_supports_gold_locator,
    gold_record_page_label,
    item_matches_citation,
    locator_pages_are_alignment_candidates,
)


def citation_recall_score(
    predicted_citations: list[str],
    gold_evidence: list[dict[str, object]],
    *,
    evidence_bundle: dict[str, object] | None = None,
    retrieved_hits: list[dict[str, object]] | None = None,
) -> float | None:
    gold_records = _gold_citation_records(gold_evidence)
    if not gold_records:
        return None
    matches = sum(
        1
        for record in gold_records
        if _gold_citation_record_matched(
            record,
            predicted_citations,
            evidence_bundle=evidence_bundle,
            retrieved_hits=retrieved_hits,
        )
    )
    return matches / len(gold_records)


def citation_precision_score(
    predicted_citations: list[str],
    gold_evidence: list[dict[str, object]],
    *,
    evidence_bundle: dict[str, object] | None = None,
    retrieved_hits: list[dict[str, object]] | None = None,
) -> float | None:
    gold_records = _gold_citation_records(gold_evidence)
    if not gold_records:
        return None
    predicted = {str(item).strip() for item in predicted_citations if str(item).strip()}
    if not predicted:
        return None
    matches = sum(
        1
        for citation in predicted
        if _predicted_citation_matched(
            citation,
            gold_records,
            evidence_bundle=evidence_bundle,
            retrieved_hits=retrieved_hits,
        )
    )
    return matches / len(predicted)


def _gold_citation_records(
    gold_evidence: list[dict[str, object]],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for item in gold_evidence:
        citation = str(item.get("citation") or item.get("source") or "").strip()
        source_id = str(item.get("document_id") or item.get("source_id") or "").strip()
        span = str(
            item.get("span")
            or item.get("text")
            or item.get("quote")
            or item.get("evidence")
            or item.get("image_quote")
            or item.get("visual_quote")
            or ""
        ).strip()
        if citation or source_id or span:
            records.append(
                {
                    "citation": citation,
                    "source_id": source_id,
                    "span": span,
                    "document_id": source_id,
                    "page": item.get("page"),
                    "page_label": item.get("page_label"),
                }
            )
    return records


def _gold_citation_record_matched(
    record: dict[str, object],
    predicted_citations: list[str],
    *,
    evidence_bundle: dict[str, object] | None,
    retrieved_hits: list[dict[str, object]] | None,
) -> bool:
    predicted = {str(item).strip() for item in predicted_citations if str(item).strip()}
    citation = str(record.get("citation") or "").strip()
    if citation and citation in predicted:
        return True
    return any(
        _predicted_citation_supports_gold_record(
            citation_text,
            record,
            evidence_bundle=evidence_bundle,
            retrieved_hits=retrieved_hits,
        )
        for citation_text in predicted
    )


def _predicted_citation_matched(
    citation: str,
    gold_records: list[dict[str, object]],
    *,
    evidence_bundle: dict[str, object] | None,
    retrieved_hits: list[dict[str, object]] | None,
) -> bool:
    return any(
        str(record.get("citation") or "").strip() == citation
        or _predicted_citation_supports_gold_record(
            citation,
            record,
            evidence_bundle=evidence_bundle,
            retrieved_hits=retrieved_hits,
        )
        for record in gold_records
    )


def _predicted_citation_supports_gold_record(
    predicted_citation: str,
    record: dict[str, object],
    *,
    evidence_bundle: dict[str, object] | None,
    retrieved_hits: list[dict[str, object]] | None,
) -> bool:
    predicted_source = citation_source_id(predicted_citation)
    if not predicted_source:
        return False
    gold_sources = {
        source
        for source in (
            citation_source_id(str(record.get("citation") or "")),
            str(record.get("source_id") or "").strip(),
        )
        if source
    }
    if predicted_source not in gold_sources:
        return False
    span = str(record.get("span") or "").strip()
    if not span:
        return False
    if not locator_pages_are_alignment_candidates(
        gold_record_page_label(record),
        citation_page_label(predicted_citation),
    ):
        return False
    evidence_text = _retrieved_evidence_text_for_citation(
        predicted_citation,
        evidence_bundle=evidence_bundle,
        retrieved_hits=retrieved_hits,
    )
    if not evidence_text:
        return False
    return evidence_text_supports_gold_locator(record, evidence_text)


def _retrieved_evidence_text_for_citation(
    predicted_citation: str,
    *,
    evidence_bundle: dict[str, object] | None,
    retrieved_hits: list[dict[str, object]] | None,
) -> str:
    bundle_items = (
        evidence_bundle.get("items") if isinstance(evidence_bundle, dict) else []
    )
    evidence_items = bundle_items if isinstance(bundle_items, list) else []
    matching_items = [
        item
        for item in [*evidence_items, *(retrieved_hits or [])]
        if isinstance(item, dict) and item_matches_citation(item, predicted_citation)
    ]
    return " ".join(evidence_item_text(item) for item in matching_items)
