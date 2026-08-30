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
    observation: dict[str, Any]


def candidate_replay_context(row: Mapping[str, Any]) -> CandidateReplayContext:
    bundle = _mapping(row.get("evidence_bundle"))
    items = list(bundle.get("items") or [])
    metadata = _mapping(row.get("evidence_metadata"))
    query_plan = _mapping(metadata.get("query_plan"))
    pack = _mapping(metadata.get("qasper_canonical_semantic_pack"))
    source = _mapping(pack.get("source_packing_observation"))
    candidate = _mapping(metadata.get("qasper_candidate_generation"))
    snapshot = _mapping(source.get("source_input_snapshot"))
    if snapshot.get("contract_id") == "semantic_source_input_snapshot.v1":
        replay_items, ranked, ranked_present, max_context, reasons = _exact_replay(
            items,
            query_plan,
            snapshot,
        )
        context_source = "stage_input_snapshot"
    else:
        replay_items, ranked, ranked_present, max_context, reasons = _legacy_replay(
            items,
            source,
        )
        context_source = "legacy_source_priority_projection"
    request_drop = _non_negative_int(
        candidate.get("candidate_request_dropped_evidence_count")
    )
    if request_drop is None:
        reasons.append("candidate_request_drop_observation_missing")
    elif request_drop:
        reasons.append("candidate_request_token_budget_changed_the_pack")
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
        "query_plan_digest": canonical_digest(query_plan),
        "max_context_length": max_context,
        "historical_candidate_request_drop_count": request_drop,
        "source_observation_digest": canonical_digest(source),
    }
    observation["replay_digest"] = canonical_digest(observation)
    return CandidateReplayContext(
        items=replay_items,
        bundle_metadata=ranked_metadata,
        query_plan=query_plan,
        max_context_length=max_context,
        observation=observation,
    )


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
        and replay.get("historical_candidate_request_drop_count") == 0
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


def _exact_replay(
    items: list[Any],
    query_plan: dict[str, Any],
    snapshot: dict[str, Any],
) -> tuple[list[Any], list[dict[str, Any]], bool, int | None, list[str]]:
    reasons: list[str] = []
    expected_items = list(snapshot.get("source_items") or [])
    replay_items = _items_in_snapshot_order(items, expected_items)
    if replay_items is None:
        replay_items = list(items)
        reasons.append("source_item_snapshot_does_not_match_probe_items")
    ranked = _ranked_rows(snapshot.get("ranked_evidence"))
    ranked_present = snapshot.get("ranked_evidence_present") is True
    if canonical_digest(query_plan) != snapshot.get("query_plan_digest"):
        reasons.append("query_plan_does_not_match_stage_snapshot")
    if snapshot.get("complete") is not True:
        reasons.append("source_input_snapshot_incomplete")
    max_context = _non_negative_int(snapshot.get("max_context_length"))
    if max_context == 0:
        max_context = None
    return replay_items, ranked, ranked_present, max_context, reasons


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
        and int(trace.get(input_count_key) or 0) == len(decisions) > 0
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
