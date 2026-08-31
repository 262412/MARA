from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ktem.docqa.qasper_semantic_pack_contract import (
    QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT,
    qasper_canonical_span_universe_digest,
)

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest, is_sha256
from benchmark.qasper_causal_transaction_runtime_stages import (
    runtime_transaction_stage_payloads,
)


def causal_transaction_stage_payloads(
    prediction: Mapping[str, Any],
    debug_row: Mapping[str, Any],
    run_context: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    generator = _mapping(debug_row.get("main_candidate_generator"))
    verifier = _mapping(debug_row.get("semantic_verifier"))
    lineage = _mapping(verifier.get("semantic_data_lineage"))
    pack = _candidate_stage_pack(prediction)
    source = _mapping(pack.get("source_packing_observation"))
    construction = _mapping(lineage.get("plan_construction"))
    event = _latest_model_transaction(verifier)
    transaction = _mapping(event.get("transaction"))
    proposal_output = _mapping(transaction.get("proposal"))
    audit_output = _mapping(transaction.get("audit"))
    proposal_value = _latest_parsed_value(proposal_output)
    stages = {
        "dataset_and_gold": _dataset_payload(prediction, debug_row),
        "retrieval_and_ranking": _retrieval_payload(prediction),
        "candidate_input": _candidate_input_payload(generator, source),
        "proposition_spans_and_selector_universe": _selector_payload(generator, pack),
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


def _retrieval_payload(prediction: Mapping[str, Any]) -> dict[str, Any]:
    raw_records = deepcopy(prediction.get("retrieved_hits") or [])
    bundle = _mapping(prediction.get("evidence_bundle"))
    production_input_records = deepcopy(bundle.get("items") or [])
    ranking_records = deepcopy(raw_records)
    ranking_source = "retrieved_hits_order"
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
    request_projection = deepcopy(
        _mapping(generator.get("candidate_request_projection_trace"))
    )
    selected_record_ids = _selected_request_record_ids(request_projection)
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
        request_drop_count=int(generator.get("request_dropped_evidence_count") or 0),
        token_measurement=_candidate_token_measurement(generator),
        token_budget=_candidate_token_budget(generator),
        selected_record_ids=selected_record_ids,
        selected_record_ids_digest=canonical_digest(selected_record_ids),
        prompt_projection=deepcopy(
            generator.get("candidate_prompt_projection_trace") or {}
        ),
        request_projection=request_projection,
    )


def _candidate_token_measurement(generator: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "estimated_input_tokens": generator.get("estimated_input_tokens"),
        "message_tokens": generator.get("estimated_message_tokens"),
        "schema_tokens": generator.get("estimated_schema_tokens"),
        "tokenizer_identity": str(generator.get("tokenizer_identity") or ""),
        "tokenizer_method": str(generator.get("tokenizer_method") or ""),
        "tokenizer_exact": generator.get("tokenizer_exact") is True,
        "tokenizer_endpoint": str(generator.get("tokenizer_endpoint") or ""),
        "tokenizer_failed": generator.get("tokenizer_failed") is True,
        "tokenizer_failure_reason": str(
            generator.get("tokenizer_failure_reason") or ""
        ),
    }


def _candidate_token_budget(generator: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: generator.get(key)
        for key in (
            "candidate_input_token_budget",
            "max_model_len",
            "max_output_tokens",
            "token_headroom_tokens",
        )
    }


def _selected_request_record_ids(projection: Mapping[str, Any]) -> list[str]:
    return [
        str(_mapping(decision).get("evidence_id") or "")
        for decision in projection.get("decisions") or []
        if _mapping(decision).get("selected") is True
    ]


def _selector_payload(
    generator: Mapping[str, Any],
    pack: Mapping[str, Any],
) -> dict[str, Any]:
    source = _mapping(pack.get("source_packing_observation"))
    raw_records = pack.get("records")
    records = deepcopy(raw_records) if isinstance(raw_records, list) else []
    records_valid = bool(records) and all(
        isinstance(record, Mapping) for record in records
    )
    selectors = _canonical_selector_spans(records)
    raw_summaries = source.get("canonical_records")
    summaries = deepcopy(raw_summaries) if isinstance(raw_summaries, list) else []
    crosswalk = deepcopy(_mapping(source.get("selector_crosswalk")))
    projection = deepcopy(
        _mapping(generator.get("canonical_selector_projection_trace"))
    )
    pack_identity = {
        "contract_id": str(pack.get("contract_id") or ""),
        "semantic_pack_digest": str(pack.get("semantic_pack_digest") or ""),
        "span_universe_digest": str(pack.get("span_universe_digest") or ""),
        "candidate_transaction_id": str(pack.get("candidate_transaction_id") or ""),
    }
    generator_identity = {
        "contract_id": str(generator.get("canonical_semantic_pack_contract_id") or ""),
        "evidence_pack_digest": str(generator.get("evidence_pack_digest") or ""),
        "semantic_pack_digest": str(
            generator.get("canonical_semantic_pack_digest") or ""
        ),
        "span_universe_digest": str(
            generator.get("canonical_span_universe_digest") or ""
        ),
        "candidate_transaction_id": str(
            generator.get("canonical_pack_candidate_transaction_id") or ""
        ),
    }
    recomputed_span_digest = (
        qasper_canonical_span_universe_digest(records) if records_valid else ""
    )
    reasons = _selector_identity_reasons(
        pack_identity,
        generator_identity,
        recomputed_span_digest=recomputed_span_digest,
    )
    reasons.extend(
        _selector_structure_reasons(
            records,
            selectors,
            summaries,
            crosswalk,
            projection,
        )
    )
    return _payload(
        reasons,
        canonical_records=records,
        canonical_records_digest=canonical_digest(records),
        canonical_record_summaries=summaries,
        canonical_record_summaries_digest=canonical_digest(summaries),
        proposition_bearing_spans=selectors,
        proposition_bearing_spans_digest=canonical_digest(selectors),
        selector_crosswalk=crosswalk,
        selector_crosswalk_digest=str(crosswalk.get("crosswalk_digest") or ""),
        canonical_selector_projection=projection,
        canonical_semantic_pack_identity=pack_identity,
        candidate_generator_pack_identity=generator_identity,
        recomputed_selector_universe_digest=recomputed_span_digest,
        selector_universe_digest=pack_identity["span_universe_digest"],
    )


def _canonical_selector_spans(records: list[Any]) -> list[dict[str, Any]]:
    return [
        {"evidence_id": str(record.get("evidence_id") or ""), **deepcopy(selector)}
        for record in records
        if isinstance(record, Mapping)
        for selector in record.get("selectors") or []
        if isinstance(selector, Mapping)
    ]


def _selector_structure_reasons(
    records: list[Any],
    selectors: list[dict[str, Any]],
    summaries: list[Any],
    crosswalk: Mapping[str, Any],
    projection: Mapping[str, Any],
) -> list[str]:
    reasons = []
    if not records:
        reasons.append("canonical_records_missing")
    elif not all(isinstance(record, Mapping) for record in records):
        reasons.append("canonical_records_invalid")
    if not selectors:
        reasons.append("proposition_bearing_spans_missing")
    if not summaries:
        reasons.append("canonical_record_summaries_missing")
    elif len(summaries) != len(records):
        reasons.append("canonical_record_summary_count_mismatch")
    elif sum(
        len(summary.get("selector_refs") or [])
        for summary in summaries
        if isinstance(summary, Mapping)
    ) != len(selectors):
        reasons.append("canonical_record_summary_selector_count_mismatch")
    if not crosswalk:
        reasons.append("selector_crosswalk_missing")
    else:
        if crosswalk.get("complete") is not True:
            reasons.append("selector_crosswalk_incomplete")
        if crosswalk.get("canonical_selector_count") != len(selectors):
            reasons.append("selector_crosswalk_selector_count_mismatch")
    if not projection:
        reasons.append("canonical_selector_projection_missing")
    else:
        if projection.get("complete") is not True:
            reasons.append("canonical_selector_projection_incomplete")
        if projection.get("selected_selector_count") != len(selectors):
            reasons.append("canonical_selector_projection_count_mismatch")
    return reasons


def _selector_identity_reasons(
    pack: Mapping[str, str],
    generator: Mapping[str, str],
    *,
    recomputed_span_digest: str,
) -> list[str]:
    reasons = []
    if pack.get("contract_id") != QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT:
        reasons.append("canonical_semantic_pack_contract_invalid")
    for field in ("semantic_pack_digest", "span_universe_digest"):
        if not pack.get(field):
            reasons.append(f"canonical_{field}_missing")
    if not pack.get("candidate_transaction_id"):
        reasons.append("canonical_pack_candidate_transaction_id_missing")
    generator_required = {
        "contract_id": "generator_canonical_semantic_pack_contract_missing",
        "evidence_pack_digest": "generator_evidence_pack_digest_missing",
        "semantic_pack_digest": "generator_canonical_semantic_pack_digest_missing",
        "span_universe_digest": "generator_canonical_span_universe_digest_missing",
        "candidate_transaction_id": (
            "generator_canonical_pack_candidate_transaction_id_missing"
        ),
    }
    for field, reason in generator_required.items():
        if not generator.get(field):
            reasons.append(reason)
    if pack.get("contract_id") and generator.get("contract_id") != pack.get(
        "contract_id"
    ):
        reasons.append("generator_canonical_semantic_pack_contract_mismatch")
    if pack.get("semantic_pack_digest"):
        if generator.get("semantic_pack_digest") != pack.get("semantic_pack_digest"):
            reasons.append("generator_canonical_semantic_pack_digest_mismatch")
        if generator.get("evidence_pack_digest") != pack.get("semantic_pack_digest"):
            reasons.append("generator_evidence_pack_digest_mismatch")
    if pack.get("span_universe_digest"):
        if generator.get("span_universe_digest") != pack.get("span_universe_digest"):
            reasons.append("generator_canonical_span_universe_digest_mismatch")
        if recomputed_span_digest != pack.get("span_universe_digest"):
            reasons.append("canonical_span_universe_digest_mismatch")
    if pack.get("candidate_transaction_id") and generator.get(
        "candidate_transaction_id"
    ) != pack.get("candidate_transaction_id"):
        reasons.append("generator_canonical_pack_candidate_transaction_id_mismatch")
    return reasons


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


def _ranking_identity(records: list[Any]) -> list[dict[str, Any]]:
    ranking = []
    for index, record in enumerate(records):
        value = _mapping(record)
        metadata = _mapping(value.get("metadata"))
        position = value.get("ranked_position")
        if isinstance(position, bool) or not isinstance(position, int):
            position = index
        ranking.append(
            {
                "position": position,
                "canonical_id": str(
                    value.get("canonical_id") or value.get("evidence_id") or ""
                ),
                "reranker_rank": value.get(
                    "reranker_rank", metadata.get("reranker_rank")
                ),
                "reranker_score": value.get(
                    "reranker_score", metadata.get("reranker_score")
                ),
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


def _candidate_stage_pack(prediction: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _mapping(prediction.get("evidence_metadata"))
    return _mapping(metadata.get("qasper_canonical_semantic_pack"))


def _payload(reasons: list[str], **values: Any) -> dict[str, Any]:
    unique = list(dict.fromkeys(reason for reason in reasons if reason))
    return {
        "status": "complete" if not unique else "incomplete",
        "incompleteness_reasons": unique,
        **values,
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
