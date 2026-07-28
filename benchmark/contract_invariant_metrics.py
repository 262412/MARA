from __future__ import annotations

from typing import Any

from ktem.docqa.benchmark_evidence import benchmark_evidence_record
from ktem.docqa.calculation_evidence_identity import calculation_evidence_lookup
from ktem.docqa.evidence_identity import EvidenceIdentity, identity_of

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
)


def contract_invariant_summary(
    predictions: list[dict[str, Any]],
) -> dict[str, float | None]:
    metrics = [_prediction_contract_metrics(prediction) for prediction in predictions]
    return {
        "identity_collision_count": sum(
            float(value["identity_collision_count"] or 0.0) for value in metrics
        ),
        "runtime_benchmark_roundtrip": safe_mean(
            [
                value["runtime_benchmark_roundtrip"]
                for value in metrics
                if value["runtime_benchmark_roundtrip"] is not None
            ]
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
        "identity_collision_count": float(_identity_collision_count(candidates)),
        "runtime_benchmark_roundtrip": _roundtrip_rate(candidates),
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


def _identity_collision_count(items: list[dict[str, Any]]) -> int:
    identities: dict[str, EvidenceIdentity] = {}
    collisions = 0
    for item in items:
        identity = identity_of(item)
        prior = identities.get(identity.key)
        if prior is not None and prior != identity:
            collisions += 1
        identities[identity.key] = identity
        canonical_id = str(item.get("canonical_id") or "").strip()
        if canonical_id and canonical_id != identity.key:
            collisions += 1
    return collisions


def _roundtrip_rate(items: list[dict[str, Any]]) -> float | None:
    if not items:
        return None
    valid = 0
    for item in items:
        projected = benchmark_evidence_record(item).as_dict()
        if identity_of(projected) != identity_of(item):
            continue
        if any(
            item.get(field) not in (None, "")
            and str(projected.get(field)) != str(item.get(field))
            for field in _ATOMIC_ROUNDTRIP_FIELDS
        ):
            continue
        valid += 1
    return valid / len(items)


def _citation_provenance_violations(
    candidates: list[dict[str, Any]],
    cited: list[dict[str, Any]],
) -> int:
    candidate_ids = {identity_of(item).key for item in candidates}
    candidate_ids.update(calculation_evidence_lookup(candidates))
    locators = {_locator(item) for item in candidates}
    return sum(
        identity_of(item).key not in candidate_ids
        and (
            identity_of(item).kind not in {"page", "source"}
            or _locator(item) not in locators
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


def _locator(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(
            item.get("source_id")
            or item.get("file_id")
            or item.get("document_id")
            or ""
        ).strip(),
        str(item.get("page_label") or item.get("page") or "").strip(),
    )


def _records(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, dict)]
