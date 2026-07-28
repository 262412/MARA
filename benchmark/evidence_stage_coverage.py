from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_locators import (
    normalized_page_aliases,
    normalized_source_aliases,
)

EvidenceKey = tuple[str, str, str, str]


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
        "canonical_candidate_evidence_coverage": candidate_pool,
        "post_fusion_evidence_coverage": _stage_records(
            metadata,
            "fused_evidence",
        ),
        "fused_evidence_coverage": _stage_records(metadata, "fused_evidence"),
        "reranker_input_evidence_coverage": _stage_records(
            metadata,
            "reranker_input_evidence",
        ),
        "selected_evidence_coverage": _stage_records(metadata, "selected_evidence"),
        "used_evidence_coverage": _stage_records(metadata, "used_evidence"),
        "generation_context_evidence_coverage": _stage_records(
            metadata,
            "generation_context_evidence",
        ),
        "execution_operand_evidence_coverage": _stage_records(
            metadata,
            "execution_operand_evidence",
        ),
        "verified_evidence_coverage": _stage_records(metadata, "verified_evidence"),
        "verified_claim_support_evidence_coverage": _stage_records(
            metadata,
            "verified_claim_support_evidence",
        ),
        "cited_evidence_coverage": _stage_records(metadata, "cited_evidence"),
        "emitted_citation_evidence_coverage": _stage_records(
            metadata,
            "emitted_citation_evidence",
        ),
    }
    return {
        "candidate_recall_at_50": evidence_coverage(candidates, prediction, gold),
        "candidate_page_coverage_at_50": _page_coverage(
            candidates,
            _gold_page_keys(prediction),
        ),
        "candidate_pool_recall_at_80": evidence_coverage(
            candidate_pool[:80] if candidate_pool is not None else None,
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
            if (key := _record_key(item)) != ("", "", "", "")
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
            and (not key[3] or key[3] == candidate[3])
            for candidate in item_keys
        )
    }


def reranked_trace_available(metadata: dict[str, Any]) -> bool:
    if "reranked_evidence" not in metadata:
        return False
    trace = metadata.get("ranking_trace")
    return not (isinstance(trace, dict) and trace.get("backend_execution") is False)


def _record_key(item: dict[str, Any]) -> EvidenceKey:
    identity = item.get("identity")
    identity_payload = identity if isinstance(identity, dict) else {}
    return (
        str(
            item.get("source_id")
            or item.get("document_id")
            or identity_payload.get("source_id")
            or ""
        )
        .strip()
        .lower(),
        str(item.get("page_label") or item.get("page") or "").strip().lower(),
        _record_kind(item, identity_payload).lower(),
        _record_local_id(item, identity_payload).lower(),
    )


def _item_keys(item: dict[str, Any]) -> set[EvidenceKey]:
    sources = _item_sources(item) | {""}
    pages = normalized_page_aliases(item) | {""}
    record = _record_key(item)
    kinds = {record[2], ""}
    elements = {record[3], ""}
    return {
        (source, page, kind, element)
        for source in sources
        for page in pages
        for kind in kinds
        for element in elements
    }


def _record_kind(
    item: dict[str, Any],
    identity: dict[str, Any],
) -> str:
    if identity.get("kind"):
        return str(identity["kind"])
    for field, kind in (
        ("cell_id", "cell"),
        ("span_id", "span"),
        ("element_id", "element"),
        ("evidence_id", "evidence"),
    ):
        if item.get(field):
            return kind
    return ""


def _record_local_id(
    item: dict[str, Any],
    identity: dict[str, Any],
) -> str:
    return str(
        item.get("cell_id")
        or item.get("span_id")
        or item.get("element_id")
        or item.get("evidence_id")
        or identity.get("local_id")
        or ""
    )


def _gold_page_keys(prediction: dict[str, Any]) -> set[tuple[str, str]]:
    keys = {
        (
            str(item.get("source_id") or item.get("document_id") or "").strip().lower(),
            str(item.get("page_label") or item.get("page") or "").lower(),
        )
        for item in _records(prediction.get("gold_evidence"))
        if item.get("page_label") not in (None, "")
        or item.get("page") not in (None, "")
    }
    return keys or {
        ("", str(page).strip().lower()) for page in prediction.get("gold_pages") or []
    }


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
            and page.lower() in normalized_page_aliases(item)
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
    return normalized_source_aliases(item)


def _records(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, dict)]
