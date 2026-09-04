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
        item
        for item in verifier.get("recovery_transitions") or []
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
            and _semantic_state_unchanged(transition)
        )
    if action not in {
        "reaudit_changed_proposition_binding",
        "fresh_reverification",
        "reaudit_after_state_change",
    }:
        return False
    if action == "reaudit_changed_proposition_binding":
        return _semantic_domain_change(transition, "binding") is not True
    return not _reverify_state_changed(transition)


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
    return any(
        _semantic_domain_change(event, domain) is True
        for domain in ("pack", "slot", "binding")
    )


def _semantic_state_unchanged(transition: dict[str, Any]) -> bool:
    """Require known semantic state stability before stopping recovery."""
    return all(
        _semantic_domain_change(transition, domain) is False
        for domain in ("pack", "slot", "binding")
    )


def _semantic_domain_change(
    event: dict[str, Any],
    domain: str,
) -> bool | None:
    fields, digest_pairs = _semantic_domain_fields(domain)
    observed = False
    changed = False
    for field in fields:
        if field not in event:
            continue
        observed = True
        if not isinstance(event.get(field), bool):
            return None
        changed = changed or event[field]
    for before_field, after_field in digest_pairs:
        before_present = before_field in event
        after_present = after_field in event
        if before_present != after_present:
            return None
        if not before_present:
            continue
        observed = True
        before = event.get(before_field)
        after = event.get(after_field)
        if not before or not after:
            return None
        changed = changed or before != after
    return changed if observed else None


def _semantic_domain_fields(
    domain: str,
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    return {
        "pack": (
            (
                "effective_semantic_pack_digest_changed",
                "semantic_pack_digest_changed",
            ),
            (
                (
                    "effective_semantic_pack_digest_before",
                    "effective_semantic_pack_digest_after",
                ),
                ("semantic_pack_digest_before", "semantic_pack_digest_after"),
            ),
        ),
        "slot": (
            (
                "semantic_slot_state_changed",
                "slot_state_changed",
                "slot_state_digest_changed",
                "normalized_slot_state_digest_changed",
            ),
            (
                ("slot_state_digest_before", "slot_state_digest_after"),
                (
                    "normalized_slot_state_digest_before",
                    "normalized_slot_state_digest_after",
                ),
            ),
        ),
        "binding": (
            (
                "proposition_binding_changed",
                "proposition_binding_digest_changed",
                "canonical_proposition_binding_digest_changed",
            ),
            (
                (
                    "proposition_binding_digest_before",
                    "proposition_binding_digest_after",
                ),
                (
                    "canonical_proposition_binding_digest_before",
                    "canonical_proposition_binding_digest_after",
                ),
            ),
        ),
    }[domain]
