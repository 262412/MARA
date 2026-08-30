from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest, is_sha256
from benchmark.qasper_causal_transaction_runtime_stages import (
    runtime_transaction_stage_payloads,
)


def causal_transaction_stage_payloads(
    prediction: Mapping[str, Any],
    debug_row: Mapping[str, Any],
    run_context: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    metadata = _terminal_metadata(prediction)
    generator = _mapping(debug_row.get("main_candidate_generator"))
    verifier = _mapping(debug_row.get("semantic_verifier"))
    lineage = _mapping(verifier.get("semantic_data_lineage"))
    source = _mapping(lineage.get("source_packing"))
    construction = _mapping(lineage.get("plan_construction"))
    event = _latest_model_transaction(verifier)
    transaction = _mapping(event.get("transaction"))
    proposal_output = _mapping(transaction.get("proposal"))
    audit_output = _mapping(transaction.get("audit"))
    proposal_value = _latest_parsed_value(proposal_output)
    stages = {
        "dataset_and_gold": _dataset_payload(prediction, debug_row),
        "retrieval_and_ranking": _retrieval_payload(prediction, metadata),
        "candidate_input": _candidate_input_payload(generator, source),
        "proposition_spans_and_selector_universe": _selector_payload(generator, source),
        "candidate_plans": _candidate_plans_payload(construction),
        "selected_local_plan": _selected_plan_payload(
            generator, construction, proposal_value
        ),
        "projected_plan_authority": _projection_payload(
            construction, proposal_value, verifier
        ),
    }
    stages.update(
        runtime_transaction_stage_payloads(
            prediction,
            generator,
            verifier,
            event,
            transaction,
            proposal_output,
            audit_output,
            run_context,
        )
    )
    return stages


def stage_comparison_payload(stage: str, payload: Mapping[str, Any]) -> Any:
    if stage == "retrieval_and_ranking":
        return {
            "status": payload.get("status"),
            "incompleteness_reasons": list(payload.get("incompleteness_reasons") or []),
            "raw_retrieval_records_digest": payload.get("raw_retrieval_records_digest"),
            "retrieval_trace_digest": payload.get("retrieval_trace_digest"),
            "production_input_records_digest": payload.get(
                "production_input_records_digest"
            ),
            "ranking_source": payload.get("ranking_source"),
            "ranking_digest": payload.get("ranking_digest"),
        }
    if stage != "run_provenance_and_artifact":
        return deepcopy(dict(payload))
    provenance = _mapping(payload.get("run_provenance"))
    artifact = _mapping(payload.get("artifact_binding"))
    return {
        "status": payload.get("status"),
        "incompleteness_reasons": list(payload.get("incompleteness_reasons") or []),
        "code_identity": deepcopy(provenance.get("code_identity") or {}),
        "manifest": deepcopy(provenance.get("manifest") or {}),
        "config_digest": provenance.get("config_digest"),
        "provider_model_identity": deepcopy(
            provenance.get("provider_model_identity") or {}
        ),
        "source_prediction_digest": artifact.get("source_prediction_digest"),
    }


def _dataset_payload(
    prediction: Mapping[str, Any],
    debug_row: Mapping[str, Any],
) -> dict[str, Any]:
    question = str(prediction.get("question") or debug_row.get("question") or "")
    gold = {
        "answers": deepcopy(prediction.get("gold_answers") or []),
        "evidence": deepcopy(prediction.get("gold_evidence") or []),
        "annotation_scores": deepcopy(prediction.get("qasper_annotation_scores") or []),
        "annotation_diagnostics": deepcopy(
            prediction.get("qasper_annotation_diagnostics")
            or debug_row.get("qasper_annotation_diagnostics")
            or {}
        ),
    }
    identity = {
        "example_id": str(prediction.get("example_id") or ""),
        "route": str(prediction.get("route") or ""),
        "document_id": str(prediction.get("document_id") or ""),
        "document_ids": deepcopy(prediction.get("document_ids") or []),
        "question": question,
    }
    reasons = []
    if not identity["example_id"]:
        reasons.append("example_id_missing")
    if not identity["route"]:
        reasons.append("route_missing")
    if not question:
        reasons.append("question_missing")
    if not gold["answers"]:
        reasons.append("gold_answers_missing")
    return _payload(
        reasons,
        sample_identity=identity,
        sample_identity_digest=canonical_digest(identity),
        question_digest=canonical_digest(question),
        gold=gold,
        gold_digest=canonical_digest(gold),
    )


def _retrieval_payload(
    prediction: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    raw_records = deepcopy(prediction.get("retrieved_hits") or [])
    bundle = _mapping(prediction.get("evidence_bundle"))
    production_input_records = deepcopy(bundle.get("items") or [])
    ranking_records, ranking_source = _ranking_snapshot(raw_records, metadata)
    ranking = _ranking_identity(ranking_records)
    retrieval_trace = deepcopy(prediction.get("retrieval_trace") or [])
    reasons = []
    if "retrieved_hits" not in prediction:
        reasons.append("raw_retrieval_records_missing")
    if "items" not in bundle:
        reasons.append("production_input_records_missing")
    return _payload(
        reasons,
        raw_retrieval_records=raw_records,
        raw_retrieval_records_digest=canonical_digest(raw_records),
        retrieval_trace=retrieval_trace,
        retrieval_trace_digest=canonical_digest(retrieval_trace),
        production_input_records=production_input_records,
        production_input_records_digest=canonical_digest(production_input_records),
        ranking_source=ranking_source,
        ranking_records=ranking_records,
        ranking_records_digest=canonical_digest(ranking_records),
        ranking=ranking,
        ranking_digest=canonical_digest(ranking),
    )


def _candidate_input_payload(
    generator: Mapping[str, Any],
    source: Mapping[str, Any],
) -> dict[str, Any]:
    snapshot = deepcopy(_mapping(source.get("source_input_snapshot")))
    messages = deepcopy(generator.get("message_stack") or [])
    reasons = []
    if snapshot.get("contract_id") != "semantic_source_input_snapshot.v1":
        reasons.append("source_input_snapshot_missing")
    if snapshot.get("complete") is not True:
        reasons.append("source_input_snapshot_incomplete")
    if not messages:
        reasons.append("candidate_message_stack_missing")
    if not is_sha256(generator.get("input_digest")):
        reasons.append("candidate_input_digest_missing")
    return _payload(
        reasons,
        source_input_snapshot=snapshot,
        source_input_snapshot_digest=str(snapshot.get("snapshot_digest") or ""),
        candidate_message_stack=messages,
        candidate_message_stack_digest=canonical_digest(messages),
        response_schema_digest=str(generator.get("response_schema_digest") or ""),
        candidate_input_digest=str(generator.get("input_digest") or ""),
        candidate_request_drop_count=int(
            generator.get("candidate_request_dropped_evidence_count") or 0
        ),
        prompt_projection=deepcopy(
            generator.get("candidate_prompt_projection_trace") or {}
        ),
        request_projection=deepcopy(
            generator.get("candidate_request_projection_trace") or {}
        ),
    )


def _selector_payload(
    generator: Mapping[str, Any],
    source: Mapping[str, Any],
) -> dict[str, Any]:
    records = deepcopy(source.get("canonical_records") or source.get("records") or [])
    selectors = [
        deepcopy(selector)
        for record in records
        if isinstance(record, Mapping)
        for selector in record.get("selectors") or []
        if isinstance(selector, Mapping)
    ]
    crosswalk = deepcopy(_mapping(source.get("selector_crosswalk")))
    projection = deepcopy(
        _mapping(generator.get("canonical_selector_projection_trace"))
    )
    reasons = []
    if not records:
        reasons.append("canonical_records_missing")
    if not crosswalk:
        reasons.append("selector_crosswalk_missing")
    if not projection:
        reasons.append("canonical_selector_projection_missing")
    return _payload(
        reasons,
        canonical_records=records,
        canonical_records_digest=canonical_digest(records),
        proposition_bearing_spans=selectors,
        proposition_bearing_spans_digest=canonical_digest(selectors),
        selector_crosswalk=crosswalk,
        selector_crosswalk_digest=str(crosswalk.get("crosswalk_digest") or ""),
        canonical_selector_projection=projection,
        selector_universe_digest=str(
            generator.get("canonical_span_universe_digest") or ""
        ),
    )


def _candidate_plans_payload(construction: Mapping[str, Any]) -> dict[str, Any]:
    decisions = deepcopy(construction.get("candidate_decisions") or [])
    reasons = []
    if construction.get("candidate_decisions_complete") is not True:
        reasons.append("candidate_plan_enumeration_incomplete")
    if int(construction.get("candidate_decision_count") or 0) != len(decisions):
        reasons.append("candidate_plan_count_mismatch")
    for decision in decisions:
        value = _mapping(decision)
        if value.get("decision") == "rejected" and not value.get("rejection_reasons"):
            reasons.append("rejected_plan_typed_reason_missing")
            break
    return _payload(
        reasons,
        enumeration_policy=deepcopy(construction.get("enumeration_policy") or {}),
        enumeration_policy_digest=str(
            construction.get("enumeration_policy_digest") or ""
        ),
        selector_pool_decisions=deepcopy(
            construction.get("selector_pool_decisions") or []
        ),
        selector_pool_decisions_digest=str(
            construction.get("selector_pool_decisions_digest") or ""
        ),
        candidate_plan_count=int(construction.get("candidate_count") or 0),
        legal_plan_count=int(construction.get("legal_plan_count") or 0),
        candidate_plans=decisions,
        candidate_plans_digest=str(
            construction.get("candidate_decisions_digest") or ""
        ),
        selected_candidate_ids=deepcopy(
            construction.get("selected_candidate_ids") or {}
        ),
        best_rejected_candidates=deepcopy(
            construction.get("best_rejected_candidates") or {}
        ),
    )


def _selected_plan_payload(
    generator: Mapping[str, Any],
    construction: Mapping[str, Any],
    proposal_value: Mapping[str, Any],
) -> dict[str, Any]:
    selected = str(
        proposal_value.get("canonical_evidence_plan_id")
        or construction.get("selected_plan_id")
        or ""
    )
    legal_count = int(construction.get("legal_plan_count") or 0)
    binding = _mapping(generator.get("candidate_evidence_set_binding"))
    reason = str(construction.get("reason") or "")
    status = "selected" if selected else "not_selected"
    if not selected and not reason:
        reason = "no_legal_plan" if legal_count == 0 else "model_did_not_select_plan"
    return _payload(
        [],
        selection_status=status,
        selection_reason=reason,
        selected_plan_id=selected,
        legal_plan_count=legal_count,
        selected_candidate_ids=deepcopy(
            construction.get("selected_candidate_ids") or {}
        ),
        canonical_evidence_plan=deepcopy(binding.get("canonical_evidence_plan") or {}),
    )


def _projection_payload(
    construction: Mapping[str, Any],
    proposal_value: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> dict[str, Any]:
    premises = deepcopy(proposal_value.get("premises") or [])
    slot_bindings = {
        str(premise.get("premise_ref") or f"P{index}"): deepcopy(
            premise.get("proposition_slot_bindings") or {}
        )
        for index, premise in enumerate(premises, start=1)
        if isinstance(premise, Mapping)
    }
    selected = str(
        proposal_value.get("canonical_evidence_plan_id")
        or construction.get("selected_plan_id")
        or ""
    )
    projection_status = "projected" if selected and premises else "not_projected"
    return _payload(
        [],
        projection_status=projection_status,
        projection_reason=(
            "" if projection_status == "projected" else "selected_plan_unavailable"
        ),
        selected_plan_id=selected,
        premises=premises,
        premises_digest=canonical_digest(premises),
        slot_bindings=slot_bindings,
        slot_bindings_digest=canonical_digest(slot_bindings),
        proof_mode=str(
            proposal_value.get("proof_mode") or verifier.get("proof_mode") or ""
        ),
        evidence_relation=str(proposal_value.get("evidence_relation") or ""),
    )


def _ranking_snapshot(
    raw_records: list[Any],
    metadata: Mapping[str, Any],
) -> tuple[list[Any], str]:
    for key in ("candidate_ranked_evidence", "reranked_evidence"):
        values = metadata.get(key)
        if isinstance(values, list) and values:
            return deepcopy(values), key
    ranking = [
        {
            "position": index,
            "canonical_id": str(_mapping(record).get("canonical_id") or ""),
            "reranker_rank": _mapping(record).get("reranker_rank"),
            "reranker_score": _mapping(record).get("reranker_score"),
        }
        for index, record in enumerate(raw_records)
    ]
    return ranking, "retrieved_hits_order"


def _ranking_identity(records: list[Any]) -> list[dict[str, Any]]:
    ranking = []
    for index, record in enumerate(records):
        value = _mapping(record)
        position = value.get("ranked_position")
        if isinstance(position, bool) or not isinstance(position, int):
            position = index
        ranking.append(
            {
                "position": position,
                "canonical_id": str(
                    value.get("canonical_id") or value.get("evidence_id") or ""
                ),
                "reranker_rank": value.get("reranker_rank"),
                "reranker_score": value.get("reranker_score"),
            }
        )
    return ranking


def _latest_model_transaction(verifier: Mapping[str, Any]) -> dict[str, Any]:
    trace = _mapping(verifier.get("debug_trace"))
    for event in reversed(trace.get("events") or []):
        if isinstance(event, Mapping) and event.get("event") == "model_transaction":
            return dict(event)
    return {}


def _latest_parsed_value(stage: Mapping[str, Any]) -> dict[str, Any]:
    for attempt in reversed(stage.get("attempts") or []):
        if isinstance(attempt, Mapping) and isinstance(
            attempt.get("parsed_value"), Mapping
        ):
            return dict(attempt["parsed_value"])
    return {}


def _terminal_metadata(prediction: Mapping[str, Any]) -> dict[str, Any]:
    terminal = _mapping(prediction.get("engine_terminal_evidence_bundle"))
    return _mapping(terminal.get("metadata")) or _mapping(
        prediction.get("evidence_metadata")
    )


def _payload(reasons: list[str], **values: Any) -> dict[str, Any]:
    unique = list(dict.fromkeys(reason for reason in reasons if reason))
    return {
        "status": "complete" if not unique else "incomplete",
        "incompleteness_reasons": unique,
        **values,
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
