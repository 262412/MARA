from __future__ import annotations

import hashlib
import json
from typing import Any


def changed_binding_reaudit_transition(
    packed: list[dict[str, Any]],
    slots: list[dict[str, str]],
    *,
    reason: str,
    binding_before: str,
    binding_after: str,
) -> dict[str, Any]:
    evidence_digest = _digest(packed)
    slot_digest = _digest(slots)
    return {
        "from": "semantic_audit",
        "to": "proof_repair",
        "reason": reason,
        "outcome": "pruned",
        "recovery_action": "reaudit_changed_proposition_binding",
        "evidence_digest_before": evidence_digest,
        "evidence_digest_after": evidence_digest,
        "evidence_digest_changed": False,
        "slot_state_digest_before": slot_digest,
        "slot_state_digest_after": slot_digest,
        "slot_state_digest_changed": False,
        "proposition_binding_digest_before": binding_before,
        "proposition_binding_digest_after": binding_after,
        "proposition_binding_digest_changed": True,
    }


def unchanged_recovery_transition(
    packed: list[dict[str, Any]],
    slots: list[dict[str, str]],
    *,
    source: str,
    reason: str,
    semantic_pack_digest: str,
    proposition_binding_digest: str,
) -> dict[str, Any]:
    evidence_digest = _digest(packed)
    slot_digest = _digest(slots)
    return {
        "from": source,
        "to": "stop_without_reverify",
        "reason": reason,
        "outcome": "recovery_no_progress",
        "recovery_action": "stop_without_reverify",
        "stop_reason": "recovery_no_progress",
        "semantic_pack_digest_before": semantic_pack_digest,
        "semantic_pack_digest_after": semantic_pack_digest,
        "semantic_pack_digest_changed": False,
        "evidence_digest_before": evidence_digest,
        "evidence_digest_after": evidence_digest,
        "evidence_digest_changed": False,
        "slot_state_digest_before": slot_digest,
        "slot_state_digest_after": slot_digest,
        "slot_state_digest_changed": False,
        "proposition_binding_digest_before": proposition_binding_digest,
        "proposition_binding_digest_after": proposition_binding_digest,
        "proposition_binding_digest_changed": False,
    }


def _digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
