from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from benchmark.qasper_causal_evidence_chain_utils import (
    digest_matches,
    list_values,
    mapping,
)


def digest_incompleteness_reasons(
    *,
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    source: Mapping[str, Any],
    crosswalk: Mapping[str, Any],
    construction: Mapping[str, Any],
    lineage: Mapping[str, Any],
) -> list[str]:
    checks = (
        ("source_decisions_digest_mismatch", source_digests_match(source)),
        (
            "source_input_snapshot_digest_mismatch",
            source_input_snapshot_digests_match(source),
        ),
        ("selector_crosswalk_digest_mismatch", crosswalk_digest_matches(crosswalk)),
        ("selector_projection_digest_mismatch", selector_digests_match(source)),
        (
            "canonical_selector_projection_digest_mismatch",
            canonical_selector_digest_matches(generator),
        ),
        (
            "candidate_prompt_projection_digest_mismatch",
            record_projection_digests_match(
                generator.get("candidate_prompt_projection_trace")
            ),
        ),
        (
            "candidate_request_projection_digest_mismatch",
            record_projection_digests_match(
                generator.get("candidate_request_projection_trace")
            ),
        ),
        ("plan_decision_digest_mismatch", plan_digests_match(construction)),
        (
            "model_decision_context_digest_mismatch",
            model_context_digest_matches(generator),
        ),
        (
            "model_decision_plan_digest_mismatch",
            model_plan_digest_matches(generator, construction),
        ),
        (
            "first_decisive_transition_context_digest_mismatch",
            transition_context_digest_matches(lineage),
        ),
    )
    return [reason for reason, matched in checks if not matched]


def source_input_snapshot_digests_match(source: Mapping[str, Any]) -> bool:
    snapshot = mapping(source.get("source_input_snapshot"))
    if not snapshot:
        return True
    payload = {
        key: value for key, value in snapshot.items() if key != "snapshot_digest"
    }
    return bool(
        digest_matches(payload, snapshot.get("snapshot_digest"))
        and digest_matches(
            snapshot.get("source_items"), snapshot.get("source_items_digest")
        )
        and digest_matches(
            snapshot.get("ranked_evidence"), snapshot.get("ranked_evidence_digest")
        )
        and digest_matches(
            snapshot.get("required_slots"), snapshot.get("required_slots_digest")
        )
        and digest_matches(
            snapshot.get("query_plan"), snapshot.get("query_plan_digest")
        )
    )


def candidate_input_state_digests_match(value: Mapping[str, Any]) -> bool:
    if not value:
        return True
    payload = {key: item for key, item in value.items() if key != "observation_digest"}
    return bool(
        digest_matches(payload, value.get("observation_digest"))
        and digest_matches(
            value.get("stage_ranked_evidence"),
            value.get("stage_ranked_evidence_digest"),
        )
        and digest_matches(
            value.get("terminal_ranked_evidence"),
            value.get("terminal_ranked_evidence_digest"),
        )
    )


def source_input_snapshot_complete(source: Mapping[str, Any]) -> bool:
    snapshot = mapping(source.get("source_input_snapshot"))
    items = [mapping(value) for value in list_values(snapshot.get("source_items"))]
    decisions = [
        mapping(value) for value in list_values(source.get("source_decisions"))
    ]
    ranked = [mapping(value) for value in list_values(snapshot.get("ranked_evidence"))]
    identity_keys = ("source_item_index", "evidence_id", "text_digest", "text_chars")
    aligned_items = [
        {key: decision.get(key) for key in identity_keys} for decision in decisions
    ]
    snapshot_items = [{key: item.get(key) for key in identity_keys} for item in items]
    return bool(
        snapshot.get("contract_id") == "semantic_source_input_snapshot.v1"
        and snapshot.get("complete") is True
        and int(snapshot.get("source_item_count") or 0) == len(items) == len(decisions)
        and int(snapshot.get("ranked_evidence_count") or 0) == len(ranked)
        and aligned_items == snapshot_items
        and digest_matches(items, snapshot.get("source_items_digest"))
        and digest_matches(ranked, snapshot.get("ranked_evidence_digest"))
        and digest_matches(
            snapshot.get("required_slots"), snapshot.get("required_slots_digest")
        )
        and digest_matches(
            snapshot.get("query_plan"), snapshot.get("query_plan_digest")
        )
        and digest_matches(
            str(snapshot.get("question") or "").strip(),
            snapshot.get("question_digest"),
        )
        and digest_matches(
            {key: value for key, value in snapshot.items() if key != "snapshot_digest"},
            snapshot.get("snapshot_digest"),
        )
        and all(row.get("ranked_position") == index for index, row in enumerate(ranked))
    )


def candidate_input_state_complete(
    value: Mapping[str, Any],
    source: Mapping[str, Any],
) -> bool:
    stage_rows = list_values(value.get("stage_ranked_evidence"))
    terminal_rows = list_values(value.get("terminal_ranked_evidence"))
    snapshot = mapping(source.get("source_input_snapshot"))
    return bool(
        value.get("contract_id") == "qasper_candidate_input_state_observation.v1"
        and value.get("complete") is True
        and value.get("status") in {"preserved", "drifted"}
        and int(value.get("stage_ranked_evidence_count") or 0) == len(stage_rows)
        and int(value.get("terminal_ranked_evidence_count") or 0) == len(terminal_rows)
        and value.get("source_input_snapshot_digest") == snapshot.get("snapshot_digest")
        and candidate_input_state_digests_match(value)
    )


def source_digests_match(source: Mapping[str, Any]) -> bool:
    source_decisions = list_values(source.get("source_decisions"))
    window_decisions = list_values(source.get("window_decisions"))
    if not source_decisions and not window_decisions:
        return True
    return digest_matches(
        source_decisions,
        source.get("source_decisions_digest"),
    ) and digest_matches(
        window_decisions,
        source.get("window_decisions_digest"),
    )


def crosswalk_digest_matches(crosswalk: Mapping[str, Any]) -> bool:
    if not crosswalk:
        return True
    payload = {
        key: value for key, value in crosswalk.items() if key != "crosswalk_digest"
    }
    return digest_matches(payload, crosswalk.get("crosswalk_digest"))


def selector_digests_match(source: Mapping[str, Any]) -> bool:
    records = list_values(source.get("records"))
    canonical_records = list_values(source.get("canonical_records"))
    if not records and not canonical_records:
        return True
    return all(
        projection_digest_matches(
            mapping(record).get("source_selector_projection_trace")
        )
        for record in records
    ) and all(
        projection_digest_matches(
            mapping(record).get("candidate_selector_projection_trace")
        )
        for record in canonical_records
    )


def canonical_selector_digest_matches(generator: Mapping[str, Any]) -> bool:
    trace = mapping(generator.get("canonical_selector_projection_trace"))
    return not trace or projection_digest_matches(trace)


def projection_digest_matches(value: Any) -> bool:
    trace = mapping(value)
    if not trace:
        return True
    return digest_matches(trace.get("decisions"), trace.get("decisions_digest"))


def record_projection_digests_match(value: Any) -> bool:
    trace = mapping(value)
    if not trace:
        return True
    return digest_matches(
        trace.get("decisions"),
        trace.get("decisions_digest"),
    ) and digest_matches(trace.get("attempts"), trace.get("attempts_digest"))


def plan_digests_match(construction: Mapping[str, Any]) -> bool:
    if not construction:
        return True
    return (
        digest_matches(
            construction.get("enumeration_policy"),
            construction.get("enumeration_policy_digest"),
        )
        and digest_matches(
            construction.get("selector_pool_decisions"),
            construction.get("selector_pool_decisions_digest"),
        )
        and digest_matches(
            construction.get("candidate_decisions"),
            construction.get("candidate_decisions_digest"),
        )
    )


def model_context_digest_matches(generator: Mapping[str, Any]) -> bool:
    decision = mapping(generator.get("model_decision"))
    if not decision:
        return True
    context = mapping(decision.get("decision_context"))
    return digest_matches(context, decision.get("decision_context_digest"))


def model_plan_digest_matches(
    generator: Mapping[str, Any],
    construction: Mapping[str, Any],
) -> bool:
    context = mapping(mapping(generator.get("model_decision")).get("decision_context"))
    recorded = str(context.get("plan_candidate_decisions_digest") or "")
    expected = str(construction.get("candidate_decisions_digest") or "")
    return not recorded or not expected or recorded == expected


def transition_context_digest_matches(lineage: Mapping[str, Any]) -> bool:
    transition = mapping(lineage.get("first_decisive_transition"))
    if not transition:
        return True
    return digest_matches(
        transition.get("decision_context"),
        transition.get("decision_context_digest"),
    )
