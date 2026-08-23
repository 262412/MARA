from __future__ import annotations

from typing import Any

from scripts.slurm.qasper_debug_contract_identity import _normalized_candidate
from scripts.slurm.qasper_debug_contract_support import (
    _mapping,
    terminal_metadata,
    terminal_semantic_answer,
)


def _answerable_false_abstention(prediction: dict[str, Any]) -> bool:
    answerable = any(
        _normalized_candidate(answer) in {"yes", "no"}
        or str(answer or "").strip().casefold() in {"true", "false"}
        for answer in prediction.get("gold_answers") or []
    )
    return bool(answerable and terminal_semantic_answer(prediction) == "unanswerable")

def _reverify_without_state_change_count(prediction: dict[str, Any]) -> int:
    violations = sum(
        int(event.get("stage") == "reverify" and not _reverify_state_changed(event))
        for event in _reverify_events(prediction)
    )
    return violations + sum(
        int(_recovery_transition_invalid(transition))
        for transition in _semantic_recovery_transitions(prediction)
    )


def _reverify_events(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for field in ("controller_trace", "recovery_trace", "recovery_events"):
        value = prediction.get(field)
        if isinstance(value, list):
            events.extend(item for item in value if isinstance(item, dict))
    return events


def _semantic_recovery_transitions(
    prediction: dict[str, Any],
) -> list[dict[str, Any]]:
    metadata = terminal_metadata(prediction)
    verifier = _mapping(metadata.get("semantic_proposition_verifier"))
    transitions = [
        item for item in verifier.get("recovery_transitions") or []
        if isinstance(item, dict)
    ]
    debug = _mapping(verifier.get("debug_trace"))
    for event in debug.get("events") or []:
        if not isinstance(event, dict):
            continue
        outcome = _mapping(event.get("outcome"))
        transitions.extend(
            item
            for item in outcome.get("recovery_transitions") or []
            if isinstance(item, dict) and item not in transitions
        )
        repair = _mapping(_mapping(event.get("transaction")).get("proof_repair"))
        transition = _mapping(repair.get("transition"))
        if transition and transition not in transitions:
            transitions.append(transition)
    return transitions


def _recovery_transition_invalid(transition: dict[str, Any]) -> bool:
    action = str(transition.get("recovery_action") or "")
    if action == "stop_without_reverify":
        return not (
            transition.get("stop_reason") == "recovery_no_progress"
            and _unchanged_digest(transition, "evidence")
            and _unchanged_digest(transition, "slot_state")
            and _unchanged_digest(transition, "proposition_binding")
        )
    if action != "reaudit_changed_proposition_binding":
        return False
    return not (
        _unchanged_digest(transition, "evidence")
        and _unchanged_digest(transition, "slot_state")
        and _changed_digest(transition, "proposition_binding")
    )


def _unchanged_digest(transition: dict[str, Any], name: str) -> bool:
    before = transition.get(f"{name}_digest_before")
    after = transition.get(f"{name}_digest_after")
    return bool(
        transition.get(f"{name}_digest_changed") is False
        and before
        and after
        and before == after
    )


def _changed_digest(transition: dict[str, Any], name: str) -> bool:
    before = transition.get(f"{name}_digest_before")
    after = transition.get(f"{name}_digest_after")
    return bool(
        transition.get(f"{name}_digest_changed") is True
        and before
        and after
        and before != after
    )


def _reverify_state_changed(event: dict[str, Any]) -> bool:
    for field in (
        "semantic_pack_digest_changed",
        "raw_evidence_digest_changed",
        "evidence_digest_changed",
        "semantic_slot_state_changed",
        "slot_state_changed",
        "slot_state_digest_changed",
        "proposition_binding_changed",
        "proposition_binding_digest_changed",
        "evidence_changed",
        "proposition_changed",
        "semantic_state_changed",
        "semantic_state_digest_changed",
    ):
        if event.get(field) is True:
            return True
    for before_field, after_field in (
        ("semantic_pack_digest_before", "semantic_pack_digest_after"),
        ("raw_evidence_digest_before", "raw_evidence_digest_after"),
        ("evidence_digest_before", "evidence_digest_after"),
        ("semantic_state_digest_before", "semantic_state_digest_after"),
        ("slot_state_digest_before", "slot_state_digest_after"),
        (
            "proposition_binding_digest_before",
            "proposition_binding_digest_after",
        ),
        ("proposition_digest_before", "proposition_digest_after"),
        ("authority_state_before", "authority_state_after"),
        ("authority_atoms_before", "authority_atoms_after"),
    ):
        if before_field in event or after_field in event:
            return (
                before_field in event
                and after_field in event
                and event.get(before_field) != event.get(after_field)
            )
    return False
