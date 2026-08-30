from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from ktem.docqa.boolean_evidence_scope import evidence_item_text
from ktem.docqa.evidence_identity import identity_of

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest


@dataclass(frozen=True)
class CandidateReplayContext:
    items: list[Any]
    bundle_metadata: dict[str, Any]
    query_plan: dict[str, Any]
    max_context_length: int | None
    candidate_identity: dict[str, Any]
    candidate_seed: int
    online_candidate_request: dict[str, Any]
    observation: dict[str, Any]


def candidate_replay_context(row: Mapping[str, Any]) -> CandidateReplayContext:
    bundle = _mapping(row.get("evidence_bundle"))
    items = list(bundle.get("items") or [])
    metadata = _mapping(row.get("evidence_metadata"))
    candidate = _mapping(metadata.get("qasper_candidate_generation"))
    (
        replay_items,
        ranked,
        ranked_present,
        max_context,
        query_plan,
        terminal_query_plan,
        source,
        context_source,
        query_plan_source,
        reasons,
    ) = _source_replay_inputs(items, metadata)
    (
        candidate_identity,
        candidate_seed,
        online_candidate_request,
        request_drop,
    ) = _candidate_replay_inputs(candidate, reasons)
    if not query_plan:
        reasons.append("query_plan_missing")
    ranked_metadata = (
        {"candidate_ranked_evidence": deepcopy(ranked)} if ranked_present else {}
    )
    source_items = _source_item_observations(replay_items)
    observation = {
        "contract_id": "qasper_candidate_premodel_replay.v1",
        "complete": not reasons,
        "context_source": context_source,
        "incompleteness_reasons": list(dict.fromkeys(reasons)),
        "stage_sequence": [
            "source_packing",
            "candidate_source_projection",
            "candidate_selector_limit",
            "canonical_selector_projection",
            "candidate_prompt_char_budget",
            "canonical_pack_freeze",
        ],
        "source_item_count": len(source_items),
        "source_items_digest": canonical_digest(source_items),
        "source_items": source_items,
        "ranked_evidence_present": ranked_present,
        "ranked_evidence_count": len(ranked),
        "ranked_evidence_digest": canonical_digest(ranked),
        "ranked_evidence": ranked,
        "query_plan_source": query_plan_source,
        "query_plan_digest": canonical_digest(query_plan),
        "terminal_query_plan_digest": canonical_digest(terminal_query_plan),
        "max_context_length": max_context,
        "historical_candidate_request_drop_count": request_drop,
        "candidate_identity": deepcopy(candidate_identity),
        "candidate_seed": candidate_seed,
        "online_candidate_request": deepcopy(online_candidate_request),
        "source_observation_digest": canonical_digest(source),
    }
    observation["replay_digest"] = canonical_digest(observation)
    return CandidateReplayContext(
        items=replay_items,
        bundle_metadata=ranked_metadata,
        query_plan=query_plan,
        max_context_length=max_context,
        candidate_identity=candidate_identity,
        candidate_seed=candidate_seed,
        online_candidate_request=online_candidate_request,
        observation=observation,
    )


def _source_replay_inputs(
    items: list[Any],
    metadata: Mapping[str, Any],
) -> tuple[Any, ...]:
    terminal_query_plan = _mapping(metadata.get("query_plan"))
    pack = _mapping(metadata.get("qasper_canonical_semantic_pack"))
    source = _mapping(pack.get("source_packing_observation"))
    snapshot = _mapping(source.get("source_input_snapshot"))
    if snapshot.get("contract_id") == "semantic_source_input_snapshot.v1":
        exact_replay = _exact_replay(items, snapshot)
        return (
            *exact_replay[:-1],
            terminal_query_plan,
            source,
            "stage_input_snapshot",
            "stage_input_snapshot",
            exact_replay[-1],
        )
    legacy_replay = _legacy_replay(items, source)
    reasons = legacy_replay[-1]
    reasons.append("legacy_replay_not_causally_verifiable")
    return (
        *legacy_replay[:-1],
        terminal_query_plan,
        terminal_query_plan,
        source,
        "legacy_source_priority_projection",
        "terminal_query_plan_legacy",
        reasons,
    )


def _candidate_replay_inputs(
    candidate: Mapping[str, Any],
    reasons: list[str],
) -> tuple[dict[str, Any], int, dict[str, Any], int | None]:
    identity = _candidate_identity(candidate)
    seed = _non_negative_int(candidate.get("effective_seed"))
    request = _online_candidate_request(candidate)
    if not identity.get("transaction_id"):
        reasons.append("candidate_transaction_identity_missing")
    if seed is None:
        reasons.append("candidate_seed_missing")
        seed = 0
    if not request.get("message_stack"):
        reasons.append("candidate_message_stack_missing")
    if not request.get("response_schema_digest"):
        reasons.append("candidate_response_schema_digest_missing")
    if not request.get("input_digest"):
        reasons.append("candidate_input_digest_missing")
    if canonical_digest(request.get("message_stack") or []) != request.get(
        "message_stack_digest"
    ):
        reasons.append("candidate_message_stack_digest_mismatch")
    projection = _mapping(request.get("candidate_request_projection_trace"))
    if not _projection_complete(
        projection,
        contract_id="qasper_candidate_request_projection.v1",
        input_count_key="input_record_count",
        attempts_required=True,
    ):
        reasons.append("candidate_request_projection_incomplete")
    token_measurement = _mapping(request.get("token_measurement"))
    token_measurement_complete = _frozen_token_measurement_complete(token_measurement)
    if not token_measurement_complete:
        reasons.append("candidate_token_measurement_incomplete")
    budget = _mapping(request.get("budget"))
    budget_complete = _frozen_budget_complete(budget)
    if not budget_complete:
        reasons.append("candidate_token_budget_incomplete")
    if (
        token_measurement_complete
        and budget_complete
        and int(token_measurement["estimated_input_tokens"])
        > int(budget["candidate_input_token_budget"])
    ):
        reasons.append("candidate_token_budget_exceeded")
    request_drop = _non_negative_int(
        candidate.get("candidate_request_dropped_evidence_count")
    )
    if request_drop is None:
        reasons.append("candidate_request_drop_observation_missing")
        request_drop = 0
    elif (
        int(projection.get("input_record_count") or 0)
        - int(projection.get("selected_record_count") or 0)
        != request_drop
    ):
        reasons.append("candidate_request_drop_projection_mismatch")
    total_request_drop = _non_negative_int(
        candidate.get("request_dropped_evidence_count")
    )
    if total_request_drop is None:
        reasons.append("candidate_total_request_drop_observation_missing")
    elif total_request_drop < request_drop:
        reasons.append("candidate_total_request_drop_count_mismatch")
    request["complete"] = not any(reason.startswith("candidate_") for reason in reasons)
    return identity, seed, request, request_drop


def _candidate_identity(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(candidate.get(key))
        for key in (
            "trace_group_id",
            "benchmark_route_id",
            "internal_route",
            "transaction_id",
            "attempt_id",
            "generation_sequence",
            "predecessor_transaction_id",
        )
    }


def _online_candidate_request(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "message_stack": deepcopy(candidate.get("message_stack") or []),
        "message_stack_digest": str(candidate.get("message_stack_digest") or ""),
        "response_schema_digest": str(candidate.get("response_schema_digest") or ""),
        "input_digest": str(candidate.get("input_digest") or ""),
        "candidate_request_projection_trace": deepcopy(
            candidate.get("candidate_request_projection_trace") or {}
        ),
        "candidate_request_dropped_evidence_count": candidate.get(
            "candidate_request_dropped_evidence_count"
        ),
        "request_dropped_evidence_count": candidate.get(
            "request_dropped_evidence_count"
        ),
        "token_measurement": {
            "estimated_input_tokens": candidate.get("estimated_input_tokens"),
            "message_tokens": candidate.get("estimated_message_tokens"),
            "schema_tokens": candidate.get("estimated_schema_tokens"),
            "tokenizer_identity": str(candidate.get("tokenizer_identity") or ""),
            "tokenizer_method": str(candidate.get("tokenizer_method") or ""),
            "tokenizer_exact": candidate.get("tokenizer_exact") is True,
            "tokenizer_endpoint": str(candidate.get("tokenizer_endpoint") or ""),
            "tokenizer_failed": candidate.get("tokenizer_failed") is True,
            "tokenizer_failure_reason": str(
                candidate.get("tokenizer_failure_reason") or ""
            ),
        },
        "budget": {
            "candidate_input_token_budget": candidate.get(
                "candidate_input_token_budget"
            ),
            "max_model_len": candidate.get("max_model_len"),
            "max_output_tokens": candidate.get("max_output_tokens"),
            "token_headroom_tokens": candidate.get("token_headroom_tokens"),
        },
    }


def candidate_path_replay_complete(
    replay: Mapping[str, Any],
    current_snapshot: Mapping[str, Any],
    prompt_projection: Mapping[str, Any],
    canonical_projection: Mapping[str, Any],
) -> bool:
    replay_payload = {
        key: value for key, value in replay.items() if key != "replay_digest"
    }
    replay_items = list(replay.get("source_items") or [])
    current_items = list(current_snapshot.get("source_items") or [])
    replay_ranked = list(replay.get("ranked_evidence") or [])
    current_ranked = _ranked_rows(current_snapshot.get("ranked_evidence"))
    return bool(
        replay.get("contract_id") == "qasper_candidate_premodel_replay.v1"
        and replay.get("complete") is True
        and not replay.get("incompleteness_reasons")
        and canonical_digest(replay_payload) == replay.get("replay_digest")
        and int(replay.get("source_item_count") or 0) == len(replay_items)
        and canonical_digest(replay_items) == replay.get("source_items_digest")
        and int(replay.get("ranked_evidence_count") or 0) == len(replay_ranked)
        and canonical_digest(replay_ranked) == replay.get("ranked_evidence_digest")
        and _input_rows(replay_items) == _input_rows(current_items)
        and replay.get("ranked_evidence_present")
        == current_snapshot.get("ranked_evidence_present")
        and replay_ranked == current_ranked
        and replay.get("query_plan_digest") == current_snapshot.get("query_plan_digest")
        and _mapping(replay.get("online_candidate_request")).get("complete") is True
        and _projection_complete(
            prompt_projection,
            contract_id="qasper_candidate_prompt_projection.v1",
            input_count_key="input_record_count",
            attempts_required=True,
        )
        and _projection_complete(
            canonical_projection,
            contract_id="qasper_canonical_selector_projection.v1",
            input_count_key="input_selector_count",
            attempts_required=False,
        )
    )


def candidate_request_replay_complete(
    replay_trace: Mapping[str, Any],
    online_request: Mapping[str, Any],
) -> bool:
    messages = list(replay_trace.get("message_stack") or [])
    online_messages = list(online_request.get("message_stack") or [])
    request_projection = _mapping(
        replay_trace.get("candidate_request_projection_trace")
    )
    online_projection = _mapping(
        online_request.get("candidate_request_projection_trace")
    )
    token_measurement = _mapping(online_request.get("token_measurement"))
    budget = _mapping(online_request.get("budget"))
    return bool(
        messages
        and messages == online_messages
        and canonical_digest(messages) == replay_trace.get("message_stack_digest")
        and replay_trace.get("message_stack_digest")
        == online_request.get("message_stack_digest")
        and replay_trace.get("response_schema_digest")
        == online_request.get("response_schema_digest")
        and replay_trace.get("input_digest") == online_request.get("input_digest")
        and request_projection == online_projection
        and replay_trace.get("candidate_request_dropped_evidence_count")
        == online_request.get("candidate_request_dropped_evidence_count")
        and replay_trace.get("request_dropped_evidence_count")
        == online_request.get("request_dropped_evidence_count")
        and _trace_token_measurement(replay_trace) == token_measurement
        and _trace_budget(replay_trace) == budget
        and _projection_complete(
            request_projection,
            contract_id="qasper_candidate_request_projection.v1",
            input_count_key="input_record_count",
            attempts_required=True,
        )
    )


def _frozen_token_measurement_complete(value: Mapping[str, Any]) -> bool:
    estimated = _non_negative_int(value.get("estimated_input_tokens"))
    message_tokens = _non_negative_int(value.get("message_tokens"))
    schema_tokens = _non_negative_int(value.get("schema_tokens"))
    return bool(
        value.get("tokenizer_identity")
        and value.get("tokenizer_method")
        and value.get("tokenizer_failed") is False
        and estimated is not None
        and message_tokens is not None
        and schema_tokens is not None
        and estimated == message_tokens + schema_tokens
    )


def _frozen_budget_complete(value: Mapping[str, Any]) -> bool:
    input_budget = _non_negative_int(value.get("candidate_input_token_budget"))
    max_model_len = _non_negative_int(value.get("max_model_len"))
    max_output_tokens = _non_negative_int(value.get("max_output_tokens"))
    headroom = _non_negative_int(value.get("token_headroom_tokens"))
    values = (input_budget, max_model_len, max_output_tokens, headroom)
    if any(item is None or item <= 0 for item in values):
        return False
    assert input_budget is not None
    assert max_model_len is not None
    assert max_output_tokens is not None
    assert headroom is not None
    return input_budget == max_model_len - max_output_tokens - headroom


def _trace_token_measurement(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "estimated_input_tokens": value.get("estimated_input_tokens"),
        "message_tokens": value.get("estimated_message_tokens"),
        "schema_tokens": value.get("estimated_schema_tokens"),
        "tokenizer_identity": str(value.get("tokenizer_identity") or ""),
        "tokenizer_method": str(value.get("tokenizer_method") or ""),
        "tokenizer_exact": value.get("tokenizer_exact") is True,
        "tokenizer_endpoint": str(value.get("tokenizer_endpoint") or ""),
        "tokenizer_failed": value.get("tokenizer_failed") is True,
        "tokenizer_failure_reason": str(value.get("tokenizer_failure_reason") or ""),
    }


def _trace_budget(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value.get(key)
        for key in (
            "candidate_input_token_budget",
            "max_model_len",
            "max_output_tokens",
            "token_headroom_tokens",
        )
    }


def _exact_replay(
    items: list[Any],
    snapshot: dict[str, Any],
) -> tuple[
    list[Any],
    list[dict[str, Any]],
    bool,
    int | None,
    dict[str, Any],
    list[str],
]:
    reasons: list[str] = []
    snapshot_payload = {
        key: value for key, value in snapshot.items() if key != "snapshot_digest"
    }
    if canonical_digest(snapshot_payload) != snapshot.get("snapshot_digest"):
        reasons.append("source_input_snapshot_digest_mismatch")
    expected_items = list(snapshot.get("source_items") or [])
    replay_items = _items_in_snapshot_order(items, expected_items)
    if replay_items is None:
        replay_items = list(items)
        reasons.append("source_item_snapshot_does_not_match_probe_items")
    ranked = _ranked_rows(snapshot.get("ranked_evidence"))
    ranked_present = snapshot.get("ranked_evidence_present") is True
    query_plan = _mapping(snapshot.get("query_plan"))
    if not query_plan:
        reasons.append("stage_query_plan_missing")
    elif canonical_digest(query_plan) != snapshot.get("query_plan_digest"):
        reasons.append("stage_query_plan_digest_mismatch")
    if snapshot.get("complete") is not True:
        reasons.append("source_input_snapshot_incomplete")
    max_context = _non_negative_int(snapshot.get("max_context_length"))
    if max_context == 0:
        max_context = None
    return replay_items, ranked, ranked_present, max_context, query_plan, reasons


def _legacy_replay(
    items: list[Any],
    source: dict[str, Any],
) -> tuple[list[Any], list[dict[str, Any]], bool, int | None, list[str]]:
    reasons: list[str] = []
    observations = _source_item_observations(items)
    source_records = [
        dict(value)
        for value in source.get("source_records") or []
        if isinstance(value, Mapping)
    ]
    by_id = {str(record.get("evidence_id") or ""): record for record in source_records}
    if len(by_id) != len(observations) or any(
        not _legacy_record_matches(by_id.get(item["evidence_id"]), item)
        for item in observations
    ):
        reasons.append("legacy_source_observation_does_not_cover_probe_items")
    positions: dict[int, str] = {}
    for record in source_records:
        position = _legacy_ranked_position(record)
        evidence_id = str(record.get("evidence_id") or "")
        if position is None or position in positions or not evidence_id:
            reasons.append("legacy_ranked_position_invalid")
            continue
        positions[position] = evidence_id
    ranked: list[dict[str, Any]] = []
    if positions:
        for position in range(max(positions) + 1):
            ranked.append(
                {
                    "canonical_id": positions.get(
                        position,
                        f"qasper-replay-unobserved-rank:{position}",
                    )
                }
            )
    else:
        reasons.append("legacy_ranked_positions_missing")
    item_char_limit = _non_negative_int(source.get("item_char_limit"))
    return list(items), ranked, True, item_char_limit, reasons


def _items_in_snapshot_order(
    items: list[Any],
    expected: list[Any],
) -> list[Any] | None:
    observed = _source_item_observations(items)
    by_identity = {
        (item["evidence_id"], item["text_digest"], item["text_chars"]): raw
        for item, raw in zip(observed, items)
    }
    ordered: list[Any] = []
    for value in expected:
        row = _mapping(value)
        key = (
            str(row.get("evidence_id") or ""),
            str(row.get("text_digest") or ""),
            row.get("text_chars"),
        )
        raw = by_identity.get(key)
        if raw is None:
            return None
        ordered.append(raw)
    return ordered if len(ordered) == len(items) else None


def _source_item_observations(items: list[Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        text = evidence_item_text(item)
        try:
            evidence_id = identity_of(item).key
        except ValueError:
            evidence_id = ""
        output.append(
            {
                "source_item_index": index,
                "evidence_id": evidence_id,
                "text_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text_chars": len(text),
            }
        )
    return output


def _input_rows(values: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            key: _mapping(value).get(key)
            for key in ("source_item_index", "evidence_id", "text_digest", "text_chars")
        }
        for value in values
    ]


def _legacy_record_matches(record: Any, item: Mapping[str, Any]) -> bool:
    value = _mapping(record)
    return bool(
        value
        and value.get("text_digest") == item.get("text_digest")
        and value.get("text_chars") == item.get("text_chars")
    )


def _legacy_ranked_position(record: Mapping[str, Any]) -> int | None:
    factors = _mapping(record.get("priority_factors"))
    value = factors.get("ranked_position")
    if value is None:
        priority = record.get("priority")
        value = priority[-1] if isinstance(priority, list) and priority else None
    return _non_negative_int(value)


def _ranked_rows(value: Any) -> list[dict[str, Any]]:
    values = value if isinstance(value, list) else []
    return [
        {"canonical_id": str(_mapping(row).get("canonical_id") or "")} for row in values
    ]


def _projection_complete(
    value: Mapping[str, Any],
    *,
    contract_id: str,
    input_count_key: str,
    attempts_required: bool,
) -> bool:
    trace = _mapping(value)
    decisions = list(trace.get("decisions") or [])
    attempts = list(trace.get("attempts") or [])
    attempts_complete = bool(
        not attempts_required
        or (
            attempts
            and int(trace.get("attempt_count") or 0) == len(attempts)
            and canonical_digest(attempts) == trace.get("attempts_digest")
        )
    )
    return bool(
        trace.get("contract_id") == contract_id
        and trace.get("complete") is True
        and int(trace.get(input_count_key) or 0) == len(decisions)
        and int(trace.get("decision_count") or 0) == len(decisions)
        and canonical_digest(decisions) == trace.get("decisions_digest")
        and attempts_complete
    )


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
