from __future__ import annotations

import hashlib
import json
from typing import Any

from .evidence import EvidenceBundle
from .evidence_identity import identity_of
from .retrieval_semantic_identity import semantic_retrieval_identity


def semantic_progress_evidence_ids(
    bundle: EvidenceBundle | None,
) -> list[str]:
    if bundle is None:
        return []
    return sorted({_progress_identity(item) for item in bundle.items})


def semantic_progress_slot_states(
    bundle: EvidenceBundle | None,
    slot_states: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    aliases = _progress_aliases(bundle)
    normalized = [
        {
            "slot_id": str(state.get("slot_id") or ""),
            "status": str(state.get("status") or "missing"),
            "evidence_ids": sorted(
                {
                    aliases.get(str(evidence_id), str(evidence_id))
                    for evidence_id in state.get("evidence_ids") or []
                    if str(evidence_id)
                }
            ),
        }
        for state in slot_states
    ]
    return sorted(normalized, key=lambda state: state["slot_id"])


def semantic_recovery_has_progress(
    initial_bundle: EvidenceBundle | None,
    recovered_bundle: EvidenceBundle | None,
    before_slots: list[dict[str, Any]],
    after_slots: list[dict[str, Any]],
) -> bool:
    before_ids = semantic_progress_evidence_ids(initial_bundle)
    after_ids = semantic_progress_evidence_ids(recovered_bundle)
    new_ids = [value for value in after_ids if value not in before_ids]
    return bool(
        new_ids
        or semantic_progress_slot_states(initial_bundle, before_slots)
        != semantic_progress_slot_states(recovered_bundle, after_slots)
    )


def _progress_aliases(bundle: EvidenceBundle | None) -> dict[str, str]:
    aliases: dict[str, str] = {}
    if bundle is None:
        return aliases
    for item in bundle.items:
        progress_id = _progress_identity(item)
        metadata = item.get("metadata")
        nested = metadata if isinstance(metadata, dict) else {}
        for key in (
            "evidence_id",
            "canonical_id",
            "span_id",
            "element_id",
            "doc_id",
        ):
            for container in (item, nested):
                value = str(container.get(key) or "").strip()
                if value:
                    aliases[value] = progress_id
        try:
            identity = identity_of(item)
        except ValueError:
            continue
        aliases[identity.key] = progress_id
        aliases[identity.legacy_key] = progress_id
    return aliases


def _progress_identity(item: dict[str, Any]) -> str:
    semantic = semantic_retrieval_identity(item)
    if semantic is not None:
        return semantic
    try:
        return f"retrieval-runtime:{identity_of(item).key}"
    except ValueError:
        payload = json.dumps(
            item,
            default=str,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"retrieval-unidentified:{digest}"
