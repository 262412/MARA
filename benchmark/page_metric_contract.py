from __future__ import annotations

from typing import Any

from .metrics import page_hit_score
from .mmdoc_locator_crosswalk import audited_mmdoc_page_coverage, audited_mmdoc_page_hit
from .page_alignment import evidence_aligned_page_hit_score


def page_metric_contract(prediction: dict[str, Any]) -> dict[str, Any]:
    official = _official_gold_pages(prediction)
    canonical = _canonical_gold_pages(prediction)
    strict = page_hit_score(prediction["predicted_pages"], official)
    audited_mmdoc = audited_mmdoc_page_hit(prediction)
    equivalent: float | None
    if strict == 1.0:
        equivalent = strict
    elif audited_mmdoc is not None:
        equivalent = audited_mmdoc
    else:
        equivalent = evidence_aligned_page_hit_score(
            prediction["predicted_pages"],
            canonical,
            gold_evidence=list(prediction.get("gold_evidence") or []),
            evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
            retrieved_hits=list(prediction.get("retrieved_hits") or []),
        )
    legacy_page_hit = strict if strict != 0.0 else equivalent
    return {
        "legacy_page_hit": legacy_page_hit,
        "strict_page_hit": strict,
        "equivalent_page_hit": equivalent,
        "strict_gold_page_coverage": _page_coverage(
            prediction["predicted_pages"],
            official,
        ),
        "canonical_mapped_page_coverage": _page_coverage(
            prediction["predicted_pages"],
            canonical,
        ),
        "equivalent_evidence_page_coverage": _equivalent_coverage(
            prediction,
            canonical,
            equivalent,
        ),
        "mapping_trace": _page_mapping_trace(prediction),
    }


def _page_coverage(
    predicted_pages: list[int | str],
    gold_pages: list[int | str],
) -> float | None:
    gold = {str(page).strip() for page in gold_pages if str(page).strip()}
    if not gold:
        return None
    predicted = {str(page).strip() for page in predicted_pages if str(page).strip()}
    return len(predicted & gold) / len(gold)


def _equivalent_coverage(
    prediction: dict[str, Any],
    canonical_pages: list[int | str],
    fallback: float | None,
) -> float | None:
    gold_records = [
        item
        for item in prediction.get("gold_evidence") or []
        if isinstance(item, dict)
        and item.get("page", item.get("page_label")) not in (None, "")
    ]
    if not gold_records:
        return fallback
    audited_mmdoc = audited_mmdoc_page_coverage(prediction)
    if audited_mmdoc is not None:
        return audited_mmdoc
    hits = 0
    for record in gold_records:
        page = record.get("page", record.get("page_label"))
        score = evidence_aligned_page_hit_score(
            prediction["predicted_pages"],
            [page],
            gold_evidence=[record],
            evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
            retrieved_hits=list(prediction.get("retrieved_hits") or []),
        )
        hits += int(score == 1.0)
    return (
        hits / len(gold_records)
        if gold_records
        else _page_coverage(
            prediction["predicted_pages"],
            canonical_pages,
        )
    )


def _official_gold_pages(prediction: dict[str, Any]) -> list[int | str]:
    mapped = [
        item.get(
            "dataset_page",
            item.get("page", item.get("page_label")),
        )
        for item in prediction.get("gold_evidence") or []
        if isinstance(item, dict)
        and item.get(
            "dataset_page",
            item.get("page", item.get("page_label")),
        )
        not in (None, "")
    ]
    return mapped or list(prediction.get("gold_pages") or [])


def _canonical_gold_pages(prediction: dict[str, Any]) -> list[int | str]:
    mapped = [
        item.get("page", item.get("page_label"))
        for item in prediction.get("gold_evidence") or []
        if isinstance(item, dict)
        and item.get("page", item.get("page_label")) not in (None, "")
    ]
    return mapped or list(prediction.get("gold_pages") or [])


def _page_mapping_trace(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    traces = []
    for item in prediction.get("gold_evidence") or []:
        if not isinstance(item, dict):
            continue
        mapping = item.get("page_mapping")
        if not isinstance(mapping, dict):
            continue
        traces.append(
            {
                "dataset_page": str(mapping.get("dataset_page") or ""),
                "runtime_page": str(mapping.get("runtime_page") or ""),
                "mapping_source": str(mapping.get("mapping_source") or ""),
                "mapping_confidence": float(mapping.get("mapping_confidence") or 0.0),
                "mapping_version": str(mapping.get("mapping_version") or ""),
            }
        )
    return traces
