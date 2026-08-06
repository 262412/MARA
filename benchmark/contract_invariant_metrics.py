from __future__ import annotations

from typing import Any

from ktem.docqa.benchmark_evidence import benchmark_evidence_record
from ktem.docqa.calculation_evidence_identity import calculation_evidence_lookup
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_labels import normalize_evidence_label
from ktem.docqa.evidence_locators import normalized_source_page_locators

from .contract_gate_metrics import prediction_gate_metrics
from .contract_invariant_summary import summarize_contract_invariants
from .dataset_native_scores import qasper_evidence_f1_for_prediction
from .execution_slot_contract_metrics import required_slot_reference_metrics
from .finance_contract_violation_summary import (
    query_plan_calculation_plan_state_mismatch,
    unique_finance_violation_summary,
    verified_execution_gold_discrepancy,
)
from .metrics import is_abstention_answer, numeric_tolerance_score
from .qasper_contract_invariants import qasper_contract_metric_values
from .source_join_metrics import source_join_metrics

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
    "cell_role",
    "materialization_source_id",
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
_EXACT_ATOMIC_IDENTITY_FIELDS = (
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
    "cell_role",
    "materialization_source_id",
)
_EXACT_NUMERIC_FIELDS = (
    "period",
    "period_kind",
    "value",
    "unit",
    "scale",
    "currency",
)
_LOCATOR_ROUNDTRIP_FIELDS = (
    "source_id",
    "runtime_source_id",
    "evaluation_source_id",
    "runtime_identity",
    "evaluation_identity",
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
    "runtime_source_backrefs",
    "evaluation_source_backrefs",
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
    summary = summarize_contract_invariants(metrics)
    summary.update(unique_finance_violation_summary(predictions, metrics))
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
    contract_items = _contract_evidence_items(metadata)
    slot_reference_metrics = required_slot_reference_metrics(
        prediction,
        metadata,
        contract_items,
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
        **slot_reference_metrics,
        "required_slot_false_fill_count": slot_reference_metrics[
            "slot_semantic_false_fill_count"
        ],
        "source_page_cross_join_count": float(
            _source_page_cross_joins(candidates, cited)
        ),
        "calculation_render_mismatch_count": float(
            _calculation_render_mismatch(prediction, metadata)
        ),
        "heuristic_veto_after_verified_execution_count": float(
            _heuristic_veto_after_verified_execution(prediction, metadata)
        ),
        "rounding_verification_failure_count": float(
            _rounding_verification_failure(metadata)
        ),
        **_finance_state_metrics(prediction, metadata),
        "qasper_stale_verifier_state_count": float(
            _qasper_stale_verifier_state(prediction, metadata)
        ),
        "stored_recomputed_qasper_evidence_f1_mismatch_count": float(
            _stored_recomputed_qasper_evidence_f1_mismatch(prediction)
        ),
        **qasper_contract_metric_values(
            prediction,
            metadata,
            cited=cited,
            contract_items=contract_items,
        ),
        **source_join_metrics(prediction, candidates),
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


def _stored_recomputed_qasper_evidence_f1_mismatch(
    prediction: dict[str, Any],
) -> bool:
    stored = (prediction.get("metrics") or {}).get("qasper_evidence_f1")
    if stored is None:
        return False
    recomputed = qasper_evidence_f1_for_prediction(prediction)
    if recomputed is None:
        return False
    try:
        return abs(float(stored) - float(recomputed)) > 1e-9
    except (TypeError, ValueError):
        return True


def _finance_state_metrics(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, float]:
    return {
        "query_plan_calculation_plan_state_mismatch_count": float(
            query_plan_calculation_plan_state_mismatch(metadata)
        ),
        "verified_execution_gold_discrepancy_count": float(
            verified_execution_gold_discrepancy(prediction, metadata)
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
    exact_atomic = _roundtrip_rate(items, _EXACT_ATOMIC_IDENTITY_FIELDS)
    exact_numeric = _roundtrip_rate(items, _EXACT_NUMERIC_FIELDS)
    normalized_labels = _normalized_label_roundtrip_rate(items)
    raw_labels = _roundtrip_rate(
        items,
        ("raw_row_label", "raw_column_label"),
    )
    rates = {
        "atomic_field_roundtrip_rate": _roundtrip_rate(items, _ATOMIC_ROUNDTRIP_FIELDS),
        "exact_atomic_identity_roundtrip": exact_atomic,
        "exact_numeric_field_roundtrip": exact_numeric,
        "normalized_label_roundtrip": normalized_labels,
        "raw_representation_preservation": raw_labels,
        "normalization_equivalence_count": float(
            _normalization_equivalence_count(items)
        ),
        "locator_roundtrip_rate": _roundtrip_rate(items, _LOCATOR_ROUNDTRIP_FIELDS),
        "lineage_roundtrip_rate": _roundtrip_rate(items, _LINEAGE_ROUNDTRIP_FIELDS),
        "representation_roundtrip_rate": _roundtrip_rate(
            items, _REPRESENTATION_ROUNDTRIP_FIELDS
        ),
    }
    available = [
        value
        for key, value in rates.items()
        if key != "normalization_equivalence_count" and value is not None
    ]
    rates["runtime_benchmark_roundtrip"] = min(available) if available else None
    return rates


def _normalized_label_roundtrip_rate(
    items: list[dict[str, Any]],
) -> float | None:
    if not items:
        return None
    valid = 0
    for item in items:
        projected = benchmark_evidence_record(item).as_dict()
        if identity_of(projected) != identity_of(item):
            continue
        if all(
            _label_contract_valid(item, projected, label) for label in ("row", "column")
        ):
            valid += 1
    return valid / len(items)


def _label_contract_valid(
    source: dict[str, Any],
    projected: dict[str, Any],
    label: str,
) -> bool:
    raw_field = f"raw_{label}_label"
    normalized_field = f"normalized_{label}_label"
    plain_field = f"{label}_label"
    raw = _contract_field_value(source, raw_field)
    plain = _contract_field_value(source, plain_field)
    expected = normalize_evidence_label(raw if raw not in (None, "") else plain)
    actual = str(_contract_field_value(source, normalized_field) or plain or "")
    projected_normalized = str(
        _contract_field_value(projected, normalized_field)
        or _contract_field_value(projected, plain_field)
        or ""
    )
    return actual == expected and projected_normalized == expected


def _normalization_equivalence_count(items: list[dict[str, Any]]) -> int:
    count = 0
    for item in items:
        for label in ("row", "column"):
            raw = _contract_field_value(item, f"raw_{label}_label")
            normalized = _contract_field_value(item, f"normalized_{label}_label")
            if raw not in (None, "") and str(raw) != str(normalized or ""):
                count += 1
    return count


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
    comparison = metadata.get("calculation_result_comparison")
    if isinstance(comparison, dict):
        return int(not comparison.get("matched"))
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


def _heuristic_veto_after_verified_execution(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> int:
    typed_good = str(metadata.get("typed_adequacy_status") or "") == "good"
    final_good = str(metadata.get("final_adequacy_status") or "") == "good"
    answer = str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    )
    return int(typed_good and (not final_good or is_abstention_answer(answer)))


def _rounding_verification_failure(metadata: dict[str, Any]) -> int:
    comparison = metadata.get("calculation_result_comparison")
    return int(isinstance(comparison, dict) and not comparison.get("matched"))


def _qasper_stale_verifier_state(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> int:
    terminal = prediction.get("terminal_answer_state")
    if isinstance(terminal, dict):
        final_answer = str(
            prediction.get("answer_for_scoring")
            or prediction.get("predicted_answer")
            or ""
        )
        terminal_decision = terminal.get("verify_decision")
        if _normalized_answer(terminal.get("answer")) != _normalized_answer(
            final_answer
        ):
            return 1
        if not isinstance(terminal_decision, dict):
            return 1
        if prediction.get("verify_decision") != terminal_decision:
            return 1
        if metadata.get("verify_decision") != terminal_decision:
            return 1
        return int(metadata.get("answer_dependent_state") != "terminal_answer_state.v1")
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
    normalized = " ".join(str(value or "").strip().lower().split())
    return normalized.rstrip(" .!?。！？")


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


def _records(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, dict)]
