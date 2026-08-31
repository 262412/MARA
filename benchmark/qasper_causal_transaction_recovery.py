from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ktem.docqa.question_proposition import resolve_question_proposition

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest

_CONTROLLER_RECOVERY_STAGES = {
    "evidence_rebind",
    "focused_retrieval",
    "reverify",
    "targeted_retrieval",
    "typed_boolean_generation_recovery",
}


def recovery_stage_payload(
    prediction: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> dict[str, Any]:
    controller = [
        deepcopy(event)
        for event in prediction.get("controller_trace") or []
        if isinstance(event, Mapping)
        and str(event.get("stage") or "") in _CONTROLLER_RECOVERY_STAGES
    ]
    semantic = [
        _semantic_recovery_event(
            event,
            question=str(prediction.get("question") or ""),
        )
        for event in verifier.get("recovery_transitions") or []
        if isinstance(event, Mapping)
    ]
    observations = [
        _recovery_observation(event, source="controller") for event in controller
    ] + [_recovery_observation(event, source="semantic_verifier") for event in semantic]
    reasons = _recovery_reasons(observations)
    return {
        "status": "complete" if not reasons else "incomplete",
        "incompleteness_reasons": reasons,
        "recovery_status": "observed" if observations else "not_run",
        "transition_count": len(observations),
        "transitions": observations,
        "transitions_digest": canonical_digest(observations),
    }


def _recovery_reasons(observations: list[dict[str, Any]]) -> list[str]:
    reasons = []
    for index, value in enumerate(observations, start=1):
        if not value["state_dimensions"]:
            reasons.append(f"recovery_transition_{index}_state_diff_missing")
        reasons.extend(
            f"recovery_transition_{index}_{reason}"
            for reason in value.get("validation_reasons") or []
        )
    return list(dict.fromkeys(reasons))


def _recovery_observation(
    event: Mapping[str, Any],
    *,
    source: str,
) -> dict[str, Any]:
    recorded = deepcopy(dict(event))
    validation_reasons = list(recorded.pop("_causal_validation_reasons", []))
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    for key, value in event.items():
        if key.endswith("_before"):
            before[key.removesuffix("_before")] = deepcopy(value)
        elif key.endswith("_after"):
            after[key.removesuffix("_after")] = deepcopy(value)
    dimensions = sorted(set(before) & set(after))
    before_state = {key: before[key] for key in dimensions}
    after_state = {key: after[key] for key in dimensions}
    validation_reasons.extend(
        f"{key}_changed_flag_mismatch"
        for key in dimensions
        if f"{key}_changed" in event
        and event.get(f"{key}_changed") != (before[key] != after[key])
    )
    return {
        "source": source,
        "stage": str(event.get("stage") or event.get("to") or ""),
        "action": str(event.get("recovery_action") or ""),
        "outcome": str(event.get("recovery_outcome") or event.get("outcome") or ""),
        "state_dimensions": dimensions,
        "before": before_state,
        "after": after_state,
        "before_digest": canonical_digest(before_state),
        "after_digest": canonical_digest(after_state),
        "changed": any(before[key] != after[key] for key in dimensions),
        "validation_reasons": list(dict.fromkeys(validation_reasons)),
        "recorded_event": recorded,
    }


def _semantic_recovery_event(
    event: Mapping[str, Any],
    *,
    question: str,
) -> dict[str, Any]:
    projected = deepcopy(dict(event))
    if not (
        event.get("from") == "question_proposition"
        and event.get("to") == "proposition_repair"
    ):
        return projected
    resolution = resolve_question_proposition(question)
    reasons = []
    if event.get("reason") != resolution.reason:
        reasons.append("typed_repair_reason_mismatch")
    if event.get("outcome") != resolution.status:
        reasons.append("typed_repair_outcome_mismatch")
    for field, expected in (
        ("question_proposition_before", resolution.initial.as_dict()),
        ("question_proposition_after", resolution.proposition.as_dict()),
    ):
        if field in event and event.get(field) != expected:
            reasons.append(f"{field}_mismatch")
        projected[field] = expected
    projected["state_projection_source"] = (
        "recorded_typed_state"
        if "question_proposition_before" in event
        and "question_proposition_after" in event
        else "local_question_proposition_resolution"
    )
    projected["_causal_validation_reasons"] = reasons
    return projected
