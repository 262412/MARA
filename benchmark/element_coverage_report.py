from __future__ import annotations

from typing import Any


def element_coverage_report(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    total_records = 0
    with_index = 0
    records_by_modality: dict[str, int] = {}
    records_by_source: dict[str, int] = {}
    missing_example_ids = []

    for prediction in predictions:
        records = _element_records(prediction)
        if records:
            with_index += 1
        else:
            missing_example_ids.append(str(prediction.get("example_id") or ""))
        for record in records:
            total_records += 1
            _increment(records_by_modality, _record_modality(record))
            _increment(records_by_source, _record_source(record))

    report = {
        "total_predictions": len(predictions),
        "predictions_with_element_index": with_index,
        "predictions_without_element_index": len(predictions) - with_index,
        "total_element_index_records": total_records,
        "records_by_modality": dict(sorted(records_by_modality.items())),
        "records_by_source": dict(sorted(records_by_source.items())),
        "missing_example_ids": missing_example_ids,
    }
    answer_bearing_audit = _answer_bearing_audit(predictions)
    if answer_bearing_audit["total_gold_element_references"]:
        report.update(answer_bearing_audit)
    return report


def _element_records(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = prediction.get("evidence_metadata") or {}
    if not isinstance(metadata, dict):
        return []
    return [dict(item) for item in metadata.get("element_index") or []]


def _record_modality(record: dict[str, Any]) -> str:
    return str(record.get("modality") or record.get("element_type") or "unknown")


def _record_source(record: dict[str, Any]) -> str:
    metadata = record.get("metadata") or {}
    if not isinstance(metadata, dict):
        return "unknown"
    return str(metadata.get("index_source") or metadata.get("source") or "unknown")


def _increment(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _answer_bearing_audit(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    total_gold = 0
    covered_gold = 0
    with_answer_bearing_index = 0
    audited_examples = 0
    status_counts: dict[str, int] = {}
    locator_status_counts: dict[str, int] = {}
    missing_examples: list[str] = []
    wrong_page_examples: list[str] = []
    locator_covered_gold = 0
    with_locator_aligned_index = 0

    for prediction in predictions:
        gold_refs = _gold_element_references(prediction)
        if not gold_refs:
            continue
        audited_examples += 1
        total_gold += len(gold_refs)
        records = _element_records(prediction)
        status, covered = _answer_bearing_status(gold_refs, records)
        locator_status, locator_covered = _locator_alignment_status(gold_refs, records)
        covered_gold += covered
        locator_covered_gold += locator_covered
        _increment(status_counts, status)
        _increment(locator_status_counts, locator_status)
        if status == "covered":
            with_answer_bearing_index += 1
        else:
            example_id = str(prediction.get("example_id") or "")
            missing_examples.append(example_id)
            if status == "wrong_page":
                wrong_page_examples.append(example_id)
        if locator_status == "covered":
            with_locator_aligned_index += 1

    return {
        "total_gold_element_references": total_gold,
        "gold_element_references_with_index": covered_gold,
        "predictions_with_answer_bearing_element_index": with_answer_bearing_index,
        "predictions_without_answer_bearing_element_index": (
            audited_examples - with_answer_bearing_index
        ),
        "answer_bearing_coverage_by_status": dict(sorted(status_counts.items())),
        "missing_answer_bearing_example_ids": missing_examples,
        "wrong_page_example_ids": wrong_page_examples,
        "gold_element_references_with_locator_alignment": locator_covered_gold,
        "predictions_with_locator_aligned_element_index": with_locator_aligned_index,
        "predictions_without_locator_aligned_element_index": (
            audited_examples - with_locator_aligned_index
        ),
        "answer_bearing_locator_alignment_by_status": dict(
            sorted(locator_status_counts.items())
        ),
    }


def _gold_element_references(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for item in prediction.get("gold_evidence") or []:
        if not isinstance(item, dict):
            continue
        page = _normalize_page(item.get("page") or item.get("page_number"))
        sources = _gold_sources(item)
        if page and sources:
            refs.append(
                {
                    "sources": sources,
                    "page": page,
                    "element_id": str(item.get("element_id") or "").strip(),
                    "element_type": _normalize_element_type(item.get("element_type")),
                }
            )
    return refs


def _answer_bearing_status(
    gold_refs: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> tuple[str, int]:
    if not records:
        return "missing_index", 0
    covered = sum(
        1
        for gold_ref in gold_refs
        if any(_record_matches_gold(record, gold_ref) for record in records)
    )
    if covered:
        return "covered", covered
    if any(
        _record_source_matches(record, gold_ref)
        and _record_type_matches(record, gold_ref)
        for gold_ref in gold_refs
        for record in records
    ):
        return "wrong_page", 0
    if any(
        _record_source_matches(record, gold_ref)
        for gold_ref in gold_refs
        for record in records
    ):
        return "wrong_element_type", 0
    return "wrong_source", 0


def _record_matches_gold(record: dict[str, Any], gold_ref: dict[str, Any]) -> bool:
    return (
        _record_source_matches(record, gold_ref)
        and _normalize_page(gold_ref.get("page")) in _record_pages(record)
        and _record_type_matches(record, gold_ref)
    )


def _locator_alignment_status(
    gold_refs: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> tuple[str, int]:
    if not records:
        return "missing_index", 0
    covered = sum(
        1
        for gold_ref in gold_refs
        if any(_record_locator_matches_gold(record, gold_ref) for record in records)
    )
    if covered:
        return "covered", covered
    if any(
        _record_source_matches(record, gold_ref)
        and _record_locator_identity_matches(record, gold_ref)
        for gold_ref in gold_refs
        for record in records
    ):
        return "wrong_page", 0
    if any(
        _record_source_matches(record, gold_ref)
        for gold_ref in gold_refs
        for record in records
    ):
        return "wrong_element_type", 0
    return "wrong_source", 0


def _record_locator_matches_gold(
    record: dict[str, Any], gold_ref: dict[str, Any]
) -> bool:
    return (
        _record_source_matches(record, gold_ref)
        and _normalize_page(gold_ref.get("page")) in _record_pages(record)
        and _record_locator_identity_matches(record, gold_ref)
    )


def _record_locator_identity_matches(
    record: dict[str, Any], gold_ref: dict[str, Any]
) -> bool:
    gold_id = str(gold_ref.get("element_id") or "").strip()
    if gold_id and gold_id in _record_element_ids(record):
        return True
    gold_type = _normalize_element_type(gold_ref.get("element_type"))
    return not gold_type or gold_type in _record_element_types_with_aliases(record)


def _record_source_matches(record: dict[str, Any], gold_ref: dict[str, Any]) -> bool:
    return bool(_record_sources(record) & set(gold_ref.get("sources") or []))


def _record_type_matches(record: dict[str, Any], gold_ref: dict[str, Any]) -> bool:
    gold_type = _normalize_element_type(gold_ref.get("element_type"))
    return not gold_type or gold_type in _record_element_types(record)


def _gold_sources(item: dict[str, Any]) -> set[str]:
    sources = {
        _normalize_source(item.get("document_id")),
        _normalize_source(item.get("source_id")),
        _normalize_source(item.get("citation")),
    }
    return sources - {""}


def _record_sources(record: dict[str, Any]) -> set[str]:
    return {
        _normalize_source(record.get("document_id")),
        _normalize_source(record.get("source_id")),
        _normalize_source(record.get("file_id")),
        _normalize_source(record.get("file_name")),
        _normalize_source(record.get("source_name")),
    } - {""}


def _record_pages(record: dict[str, Any]) -> set[str]:
    return {
        _normalize_page(record.get("page")),
        _normalize_page(record.get("page_label")),
        _normalize_page(record.get("page_number")),
    } - {""}


def _record_element_types(record: dict[str, Any]) -> set[str]:
    return {
        _normalize_element_type(record.get("element_type")),
        _normalize_element_type(record.get("modality")),
        _normalize_element_type(record.get("type")),
    } - {""}


def _record_element_types_with_aliases(record: dict[str, Any]) -> set[str]:
    metadata = record.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    values = [
        record.get("element_type"),
        record.get("modality"),
        record.get("type"),
        record.get("element_type_aliases"),
        metadata.get("element_type_aliases"),
    ]
    return {
        _normalize_element_type(item)
        for value in values
        for item in _iter_values(value)
    } - {""}


def _record_element_ids(record: dict[str, Any]) -> set[str]:
    metadata = record.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    values = [
        record.get("element_id"),
        record.get("id"),
        record.get("element_id_aliases"),
        metadata.get("element_id_aliases"),
    ]
    return {
        str(item or "").strip()
        for value in values
        for item in _iter_values(value)
        if str(item or "").strip()
    }


def _iter_values(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _normalize_page(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _normalize_source(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "#" in text:
        text = text.split("#", 1)[0]
    text = text.rsplit("/", 1)[-1]
    return text.removesuffix(".pdf")


def _normalize_element_type(value: Any) -> str:
    element_type = str(value or "").strip().lower()
    if element_type in {"image", "fig", "chart", "plot"}:
        return "figure"
    return element_type
