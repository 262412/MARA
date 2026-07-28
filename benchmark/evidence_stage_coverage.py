from __future__ import annotations

from typing import Any

EvidenceKey = tuple[str, str, str]


def stage_coverage_values(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    *,
    candidates: list[dict[str, Any]] | None,
    candidate_pool: list[dict[str, Any]] | None,
    reranked: list[dict[str, Any]] | None,
    gold: set[EvidenceKey],
) -> dict[str, float | None]:
    stages = {
        "selected_evidence_coverage": _stage_records(metadata, "selected_evidence"),
        "used_evidence_coverage": _stage_records(metadata, "used_evidence"),
        "verified_evidence_coverage": _stage_records(metadata, "verified_evidence"),
        "cited_evidence_coverage": _stage_records(metadata, "cited_evidence"),
    }
    return {
        "candidate_recall_at_50": evidence_coverage(candidates, prediction, gold),
        "candidate_page_coverage_at_50": _page_coverage(
            candidates,
            _gold_page_keys(prediction),
        ),
        "candidate_pool_recall_at_80": evidence_coverage(
            candidate_pool,
            prediction,
            gold,
        ),
        "reranked_recall_at_10": evidence_coverage(reranked, prediction, gold),
        **{
            metric: evidence_coverage(items, prediction, gold)
            for metric, items in stages.items()
        },
    }


def gold_requirement_keys(
    prediction: dict[str, Any],
) -> list[set[EvidenceKey]]:
    requirements: list[set[EvidenceKey]] = []
    for requirement in _records(prediction.get("gold_evidence_requirements")):
        acceptable = {
            key
            for item in _records(requirement.get("acceptable_evidence"))
            if (key := _record_key(item)) != ("", "", "")
        }
        if acceptable:
            requirements.append(acceptable)
    return requirements


def evidence_coverage(
    items: list[dict[str, Any]] | None,
    prediction: dict[str, Any],
    gold: set[EvidenceKey],
) -> float | None:
    requirements = gold_requirement_keys(prediction)
    if not requirements:
        return evidence_recall(items, gold)
    if items is None:
        return None
    matched = sum(
        any(matched_gold(item, acceptable) for item in items)
        for acceptable in requirements
    )
    return matched / len(requirements)


def evidence_recall(
    items: list[dict[str, Any]] | None,
    gold: set[EvidenceKey],
) -> float | None:
    if items is None or not gold:
        return None
    if not items:
        return 0.0
    hits = set().union(*(matched_gold(item, gold) for item in items))
    return len(hits) / len(gold)


def matched_gold(
    item: dict[str, Any],
    gold: set[EvidenceKey],
) -> set[EvidenceKey]:
    item_keys = _item_keys(item)
    return {
        key
        for key in gold
        if any(
            (not key[0] or key[0] == candidate[0])
            and (not key[1] or key[1] == candidate[1])
            and (not key[2] or key[2] == candidate[2])
            for candidate in item_keys
        )
    }


def reranked_trace_available(metadata: dict[str, Any]) -> bool:
    if "reranked_evidence" not in metadata:
        return False
    trace = metadata.get("ranking_trace")
    return not (isinstance(trace, dict) and trace.get("backend_execution") is False)


def _record_key(item: dict[str, Any]) -> EvidenceKey:
    return (
        str(item.get("source_id") or item.get("document_id") or ""),
        str(item.get("page_label") or item.get("page") or ""),
        str(
            item.get("cell_id")
            or item.get("span_id")
            or item.get("element_id")
            or item.get("evidence_id")
            or ""
        ),
    )


def _item_keys(item: dict[str, Any]) -> set[EvidenceKey]:
    sources = _item_sources(item) | {""}
    pages = {str(item.get("page_label") or item.get("page") or ""), ""}
    elements = {_record_key(item)[2], ""}
    return {
        (source, page, element)
        for source in sources
        for page in pages
        for element in elements
    }


def _gold_page_keys(prediction: dict[str, Any]) -> set[tuple[str, str]]:
    keys = {
        (
            str(item.get("source_id") or item.get("document_id") or ""),
            str(item.get("page_label") or item.get("page") or ""),
        )
        for item in _records(prediction.get("gold_evidence"))
        if item.get("page_label") not in (None, "")
        or item.get("page") not in (None, "")
    }
    return keys or {("", str(page)) for page in prediction.get("gold_pages") or []}


def _page_coverage(
    items: list[dict[str, Any]] | None,
    gold_pages: set[tuple[str, str]],
) -> float | None:
    if items is None or not gold_pages:
        return None
    matched = {
        (source, page)
        for source, page in gold_pages
        if any(
            (not source or source in _item_sources(item))
            and str(item.get("page_label") or item.get("page") or "") == page
            for item in items
        )
    }
    return len(matched) / len(gold_pages)


def _stage_records(
    metadata: dict[str, Any],
    key: str,
) -> list[dict[str, Any]] | None:
    return _records(metadata.get(key)) if key in metadata else None


def _item_sources(item: dict[str, Any]) -> set[str]:
    sources = {
        str(item.get("source_id") or ""),
        str(item.get("document_id") or ""),
    }
    source_name = str(item.get("source_name") or item.get("file_name") or "")
    if source_name:
        filename = source_name.rsplit("/", 1)[-1]
        sources.add(filename.rsplit(".", 1)[0])
    for source_ref in item.get("source_backrefs") or []:
        sources.add(str(source_ref or "").split("#", 1)[0])
    return {source for source in sources if source}


def _records(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, dict)]
