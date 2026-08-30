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
