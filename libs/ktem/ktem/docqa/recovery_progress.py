from __future__ import annotations

import hashlib
import json
from typing import Any

from .boolean_evidence_scope import evidence_item_text
from .evidence import EvidenceBundle
from .evidence_identity import identity_of
from .retrieval_semantic_identity import semantic_retrieval_identity


def semantic_recovery_pack_digest(request: Any, bundle: EvidenceBundle | None) -> str:
    if bundle is None:
        return ""
    from ktem.reasoning.mara_semantic_proposition_packing import (
        required_semantic_proposition_slots,
        semantic_pack_digest_for_bundle,
    )

    from .query_planning import request_planning_question

    if not required_semantic_proposition_slots(request):
        return ""
    return semantic_pack_digest_for_bundle(
        request,
        request_planning_question(request),
        bundle,
    )


def semantic_raw_evidence_digest(bundle: EvidenceBundle | None) -> str:
    if bundle is None:
        return ""
    records: list[dict[str, Any]] = []
    for item in bundle.items:
        try:
            canonical_id = identity_of(item).key
        except ValueError:
            canonical_id = ""
        metadata = item.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        records.append(
            {
                "canonical_id": canonical_id,
                "source_id": str(
                    item.get("source_id") or metadata.get("source_id") or ""
                ),
                "page_label": str(
                    item.get("page_label") or metadata.get("page_label") or ""
                ),
                "section_id": str(
                    item.get("section_id") or metadata.get("section_id") or ""
                ),
                "canonical_start": item.get("canonical_start"),
                "canonical_end": item.get("canonical_end"),
                "modality": str(
                    item.get("modality") or metadata.get("modality") or "text"
                ),
                "text": evidence_item_text(item),
            }
        )
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def semantic_progress_evidence_ids(
    bundle: EvidenceBundle | None,
) -> list[str]:
    if bundle is None:
        return []
    return sorted({_progress_identity(item) for item in bundle.items})


def canonical_recovery_evidence_ids(
    bundle: EvidenceBundle | None,
) -> list[str]:
    if bundle is None:
        return []
    values: set[str] = set()
    for item in bundle.items:
        try:
            values.add(identity_of(item).key)
        except ValueError:
            continue
    return sorted(values)


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
