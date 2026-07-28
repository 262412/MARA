from __future__ import annotations

from typing import Any

from ktem.docqa.benchmark_evidence import benchmark_evidence_record
from ktem.docqa.calculation_evidence_identity import calculation_evidence_lookup
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_locators import normalized_source_page_locators

from .evidence_identity_metrics import reranker_lineage
from .metrics import is_abstention_answer, safe_mean

_ATOMIC_ROUNDTRIP_FIELDS = (
    "cell_id",
    "span_id",
    "evidence_level",
    "table_id",
    "row_index",
    "column_index",
    "row_label",
    "column_label",
    "period",
    "period_kind",
    "value",
    "unit",
    "scale",
    "currency",
    "statement_kind",
    "financial_scope",
    "continuation_id",
    "neighbor_element_ids",
)
_LOCATOR_ROUNDTRIP_FIELDS = (
    "source_id",
    "runtime_source_id",
    "source_aliases",
    "page_label",
    "dataset_page",
    "parser_page_index",
    "page_aliases",
    "element_id",
    "figure_label",
    "table_label",
    "bbox",
    "source_backrefs",
)
_LINEAGE_ROUNDTRIP_FIELDS = ("retrieval_lineage",)
_REPRESENTATION_ROUNDTRIP_FIELDS = (
    "representations",
    "caption",
    "ocr_text",
    "vlm_text",
)


def contract_invariant_summary(
    predictions: list[dict[str, Any]],
) -> dict[str, float | None]:
    metrics = [_prediction_contract_metrics(prediction) for prediction in predictions]
    return {
        "duplicate_identity_count": _sum_metric(metrics, "duplicate_identity_count"),
        "conflicting_identity_count": _sum_metric(
            metrics,
            "conflicting_identity_count",
        ),
        "canonical_id_mismatch_count": _sum_metric(
            metrics,
            "canonical_id_mismatch_count",
        ),
        "atomic_field_roundtrip_rate": _mean_metric(
            metrics, "atomic_field_roundtrip_rate"
        ),
        "locator_roundtrip_rate": _mean_metric(metrics, "locator_roundtrip_rate"),
        "lineage_roundtrip_rate": _mean_metric(metrics, "lineage_roundtrip_rate"),
        "representation_roundtrip_rate": _mean_metric(
            metrics,
            "representation_roundtrip_rate",
        ),
        "identity_collision_count": _sum_metric(metrics, "identity_collision_count"),
        "runtime_benchmark_roundtrip": _mean_metric(
            metrics,
            "runtime_benchmark_roundtrip",
        ),
        "citation_provenance_violation_count": sum(
            float(value["citation_provenance_violation_count"] or 0.0)
            for value in metrics
        ),
        "reranker_lineage_violation_count": sum(
            float(value["reranker_lineage_violation_count"] or 0.0) for value in metrics
        ),
        "missing_execution_slot_answer_count": sum(
            float(value["missing_execution_slot_answer_count"] or 0.0)
            for value in metrics
        ),
    }


def _prediction_contract_metrics(
    prediction: dict[str, Any],
) -> dict[str, float | None]:
    metadata = dict(prediction.get("evidence_metadata") or {})
    candidates = _records(
        metadata.get("canonical_candidate_evidence")
        or metadata.get("candidate_evidence")
    )
    reranker_input = _records(metadata.get("reranker_input_evidence"))
    reranked = _records(metadata.get("reranked_evidence"))
    cited = _records(
        metadata.get("emitted_citation_evidence") or metadata.get("cited_evidence")
    )
    return {
        **_identity_contract_metrics(candidates),
        **_roundtrip_metrics(candidates),
        "citation_provenance_violation_count": float(
            _citation_provenance_violations(candidates, cited)
        ),
        "reranker_lineage_violation_count": float(
            reranker_lineage(reranker_input, reranked)[1]
            if reranker_input and reranked
            else 0
        ),
        "missing_execution_slot_answer_count": float(
            _answered_with_missing_execution_slot(prediction, metadata)
        ),
    }


def _identity_contract_metrics(
    items: list[dict[str, Any]],
) -> dict[str, float]:
    groups: dict[str, list[dict[str, Any]]] = {}
    canonical_mismatches = 0
    for item in items:
        identity = identity_of(item)
        groups.setdefault(identity.key, []).append(item)
        canonical_id = str(item.get("canonical_id") or "").strip()
        if canonical_id and canonical_id != identity.key:
            canonical_mismatches += 1
    duplicate_count = sum(max(0, len(group) - 1) for group in groups.values())
    conflicting_count = sum(
        max(0, len({_fact_signature(item) for item in group}) - 1)
        for group in groups.values()
    )
    return {
        "duplicate_identity_count": float(duplicate_count),
        "conflicting_identity_count": float(conflicting_count),
        "canonical_id_mismatch_count": float(canonical_mismatches),
        "identity_collision_count": float(conflicting_count + canonical_mismatches),
    }


def _roundtrip_metrics(
    items: list[dict[str, Any]],
) -> dict[str, float | None]:
    rates = {
        "atomic_field_roundtrip_rate": _roundtrip_rate(items, _ATOMIC_ROUNDTRIP_FIELDS),
        "locator_roundtrip_rate": _roundtrip_rate(items, _LOCATOR_ROUNDTRIP_FIELDS),
        "lineage_roundtrip_rate": _roundtrip_rate(items, _LINEAGE_ROUNDTRIP_FIELDS),
        "representation_roundtrip_rate": _roundtrip_rate(
            items, _REPRESENTATION_ROUNDTRIP_FIELDS
        ),
    }
    available = [value for value in rates.values() if value is not None]
    rates["runtime_benchmark_roundtrip"] = min(available) if available else None
    return rates


def _roundtrip_rate(
    items: list[dict[str, Any]],
    fields: tuple[str, ...],
) -> float | None:
    if not items:
        return None
    valid = 0
    for item in items:
        projected = benchmark_evidence_record(item).as_dict()
        if identity_of(projected) != identity_of(item):
            continue
        if any(not _field_roundtrips(item, projected, field) for field in fields):
            continue
        valid += 1
    return valid / len(items)


def _citation_provenance_violations(
    candidates: list[dict[str, Any]],
    cited: list[dict[str, Any]],
) -> int:
    candidate_ids = {identity_of(item).key for item in candidates}
    candidate_ids.update(calculation_evidence_lookup(candidates))
    locators = set().union(
        *(normalized_source_page_locators(item) for item in candidates)
    )
    return sum(
        identity_of(item).key not in candidate_ids
        and (
            identity_of(item).kind not in {"page", "source"}
            or not (normalized_source_page_locators(item) & locators)
        )
        for item in cited
    )


def _answered_with_missing_execution_slot(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> bool:
    query_plan = dict(metadata.get("query_plan") or {})
    missing = [
        slot
        for slot in query_plan.get("evidence_slots") or []
        if isinstance(slot, dict)
        and slot.get("required_for_execution")
        and (
            str(slot.get("status") or "") != "filled"
            or not list(slot.get("evidence_ids") or [])
        )
    ]
    answer = str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    ).strip()
    return bool(missing and answer and not is_abstention_answer(answer))


def _field_roundtrips(
    source: dict[str, Any],
    projected: dict[str, Any],
    field: str,
) -> bool:
    value = _contract_field_value(source, field)
    if value in (None, "", [], {}):
        return True
    return _stable(value) == _stable(_contract_field_value(projected, field))


def _contract_field_value(item: dict[str, Any], field: str) -> Any:
    value = item.get(field)
    if value not in (None, "", [], {}):
        return value
    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        return value
    nested = metadata.get("metadata")
    if isinstance(nested, dict) and nested.get(field) not in (None, "", [], {}):
        return nested[field]
    return metadata.get(field)


def _fact_signature(item: dict[str, Any]) -> tuple[str, ...]:
    fields = (
        "text",
        "period",
        "period_kind",
        "value",
        "unit",
        "scale",
        "currency",
        "statement_kind",
        "financial_scope",
    )
    return tuple(_stable(item.get(field)) for field in fields)


def _stable(value: Any) -> str:
    if isinstance(value, dict):
        return repr(sorted((str(key), _stable(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return repr([_stable(item) for item in value])
    return str(value)


def _sum_metric(
    metrics: list[dict[str, float | None]],
    key: str,
) -> float:
    return sum(float(metric.get(key) or 0.0) for metric in metrics)


def _mean_metric(
    metrics: list[dict[str, float | None]],
    key: str,
) -> float | None:
    return safe_mean(
        [value for metric in metrics if (value := metric.get(key)) is not None]
    )


def _records(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, dict)]
