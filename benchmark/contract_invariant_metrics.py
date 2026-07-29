from __future__ import annotations

from typing import Any

from ktem.docqa.benchmark_evidence import benchmark_evidence_record
from ktem.docqa.calculation_evidence_identity import calculation_evidence_lookup
from ktem.docqa.evidence_alias_lookup import unambiguous_evidence_alias_lookup
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_locators import normalized_source_page_locators
from ktem.docqa.query_plan_schema import plan_from_payload
from ktem.docqa.query_planning import score_evidence_for_slot
from ktem.docqa.source_identity_crosswalk import SourceIdentityResolver

from .contract_gate_metrics import contract_gate_summary, prediction_gate_metrics
from .metrics import is_abstention_answer, numeric_tolerance_score, safe_mean

_ATOMIC_ROUNDTRIP_FIELDS = (
    "cell_id",
    "span_id",
    "evidence_level",
    "table_id",
    "table_instance_id",
    "table_group_id",
    "block_id",
    "physical_cell_identity",
    "semantic_cell_key",
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
) -> dict[str, Any]:
    metrics = [_prediction_contract_metrics(prediction) for prediction in predictions]
    summary: dict[str, Any] = {
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
        "required_slot_false_fill_count": _sum_metric(
            metrics,
            "required_slot_false_fill_count",
        ),
        "source_page_cross_join_count": _sum_metric(
            metrics,
            "source_page_cross_join_count",
        ),
        "calculation_render_mismatch_count": _sum_metric(
            metrics,
            "calculation_render_mismatch_count",
        ),
        "qasper_stale_verifier_state_count": _sum_metric(
            metrics,
            "qasper_stale_verifier_state_count",
        ),
        "gold_runtime_source_join_rate": _mean_metric(
            metrics, "gold_runtime_source_join_rate"
        ),
        "unresolved_gold_source_count": _sum_metric(
            metrics, "unresolved_gold_source_count"
        ),
        "ambiguous_source_alias_count": _sum_metric(
            metrics, "ambiguous_source_alias_count"
        ),
        "gold_runtime_source_page_join_rate": _mean_metric(
            metrics, "gold_runtime_source_page_join_rate"
        ),
    }
    summary.update(contract_gate_summary(metrics))
    return summary


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
    cited = _records(metadata.get("emitted_citation_evidence"))
    selected = _records(metadata.get("selected_evidence"))
    generation_context = _records(metadata.get("generation_context_evidence"))
    identity_metrics = _identity_contract_metrics(candidates)
    ingestion_trace = metadata.get("element_ingestion_trace")
    ingestion_conflicts = (
        int(ingestion_trace.get("identity_conflict_count") or 0)
        if isinstance(ingestion_trace, dict)
        else 0
    )
    return {
        **identity_metrics,
        "identity_collision_count": float(
            identity_metrics["identity_collision_count"] + ingestion_conflicts
        ),
        "element_ingestion_identity_conflict_count": float(ingestion_conflicts),
        **_roundtrip_metrics(candidates),
        "citation_provenance_violation_count": float(
            _citation_provenance_violations(candidates, cited)
        ),
        "missing_execution_slot_answer_count": float(
            _answered_with_missing_execution_slot(prediction, metadata)
        ),
        "required_slot_false_fill_count": float(
            _required_slot_false_fills(prediction, metadata)
        ),
        "source_page_cross_join_count": float(
            _source_page_cross_joins(candidates, cited)
        ),
        "calculation_render_mismatch_count": float(
            _calculation_render_mismatch(prediction, metadata)
        ),
        "qasper_stale_verifier_state_count": float(
            _qasper_stale_verifier_state(prediction, metadata)
        ),
        **_source_join_metrics(prediction, candidates),
        **prediction_gate_metrics(
            prediction,
            metadata,
            candidates=candidates,
            reranker_input=reranker_input,
            reranked=reranked,
            selected=selected,
            generation_context=generation_context,
        ),
    }


def _source_join_metrics(
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
    gold_sources = {
        str(item.get("source_id") or item.get("document_id") or "").strip()
        for item in gold_records
        if str(item.get("source_id") or item.get("document_id") or "").strip()
    }
    gold_sources.update(
        str(value).split("#", 1)[0].strip()
        for value in prediction.get("gold_sources") or []
        if str(value).strip()
    )
    resolved_sources = {source for source in gold_sources if resolver.resolve(source)}
    source_join_rate = (
        len(resolved_sources) / len(gold_sources) if gold_sources else None
    )
    candidate_pairs = set().union(
        *(normalized_source_page_locators(item) for item in candidates)
    )
    canonical_candidate_pairs = {
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
    page_join_rate = (
        sum(pair in canonical_candidate_pairs for pair in gold_pairs) / len(gold_pairs)
        if gold_pairs
        else None
    )
    return {
        "gold_runtime_source_join_rate": source_join_rate,
        "unresolved_gold_source_count": float(
            len(gold_sources) - len(resolved_sources)
        ),
        "ambiguous_source_alias_count": float(resolver.ambiguous_alias_count),
        "gold_runtime_source_page_join_rate": page_join_rate,
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


def _required_slot_false_fills(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> int:
    payload = metadata.get("query_plan")
    if not isinstance(payload, dict) or not isinstance(
        payload.get("evidence_slots"),
        list,
    ):
        return 0
    plan = plan_from_payload(
        str(prediction.get("question") or ""),
        answer_type=str(
            payload.get("answer_type") or prediction.get("answer_type") or ""
        ),
        verification_domain=str(
            dict(payload.get("constraints") or {}).get("verification_domain")
            or prediction.get("verification_domain")
            or ""
        ),
        payload=payload,
    )
    items = _contract_evidence_items(metadata)
    lookup = unambiguous_evidence_alias_lookup(items)
    requires_structure = bool(plan.constraints.get("requires_structure"))
    violations = 0
    for slot in plan.evidence_slots:
        required = bool(
            slot.required
            or slot.required_for_retrieval
            or slot.required_for_execution
            or slot.required_for_verification
        )
        if not required or slot.status != "filled":
            continue
        resolved = [
            lookup[evidence_id]
            for evidence_id in slot.evidence_ids
            if evidence_id in lookup
        ]
        if not resolved:
            violations += 1
            continue
        if not _slot_has_match_constraints(slot):
            continue
        if not any(
            score_evidence_for_slot(
                slot,
                item,
                requires_structure=requires_structure,
            )
            > 0
            for item in resolved
        ):
            violations += 1
    return violations


def _slot_has_match_constraints(slot: Any) -> bool:
    locator = slot.locator.as_dict() if slot.locator is not None else {}
    return bool(
        locator
        or slot.entity
        or slot.metric
        or slot.period
        or slot.period_kind
        or slot.unit
        or slot.scale
        or slot.statement_kind
        or slot.financial_scope
        or slot.modality not in {"", "auto"}
    )


def _contract_evidence_items(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in (
        "canonical_candidate_evidence",
        "candidate_evidence",
        "fused_evidence",
        "reranker_input_evidence",
        "reranked_evidence",
        "selected_evidence",
        "generation_context_evidence",
        "execution_operand_evidence",
    ):
        for item in _records(metadata.get(key)):
            identity = identity_of(item).key
            if identity in seen:
                continue
            seen.add(identity)
            items.append(item)
    return items


def _source_page_cross_joins(
    candidates: list[dict[str, Any]],
    cited: list[dict[str, Any]],
) -> int:
    valid_pairs = set().union(
        *(normalized_source_page_locators(item) for item in candidates)
    )
    sources = {source for source, _page in valid_pairs if source}
    pages = {page for _source, page in valid_pairs if page}
    invalid: set[tuple[str, str]] = set()
    for item in cited:
        for source, page in normalized_source_page_locators(item):
            if (
                source
                and page
                and (source, page) not in valid_pairs
                and source in sources
                and page in pages
            ):
                invalid.add((source, page))
    return len(invalid)


def _calculation_render_mismatch(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> int:
    trace = metadata.get("finance_numeric_trace")
    if not isinstance(trace, dict):
        return 0
    execution = trace.get("calculation_execution")
    if not isinstance(execution, dict) or execution.get("status") != "ok":
        return 0
    value = str(execution.get("value") or "").strip()
    answer = str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    ).strip()
    if not value or not answer or is_abstention_answer(answer):
        return 0
    return int(numeric_tolerance_score(answer, [value]) != 1.0)


def _qasper_stale_verifier_state(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> int:
    if not isinstance(prediction.get("pre_contract_verification"), dict):
        return 0
    post = prediction.get("post_contract_verification")
    if not isinstance(post, dict):
        return 1
    final_answer = str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    )
    if _normalized_answer(post.get("answer")) != _normalized_answer(final_answer):
        return 1
    post_decision = post.get("verify_decision")
    if not isinstance(post_decision, dict):
        return 1
    if prediction.get("verify_decision") != post_decision:
        return 1
    if metadata.get("verify_decision") != post_decision:
        return 1
    return int(metadata.get("answer_dependent_state") != "post_contract_verified")


def _normalized_answer(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


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
