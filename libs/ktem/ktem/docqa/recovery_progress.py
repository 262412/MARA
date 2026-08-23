from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

from .boolean_evidence_scope import evidence_item_text
from .evidence import EvidenceBundle
from .evidence_identity import identity_of
from .retrieval_semantic_identity import semantic_retrieval_identity

_RUNTIME_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


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


def canonical_proposition_binding_digest(
    request: Any,
    bundle: EvidenceBundle | None,
) -> str:
    """Return the canonical digest for the proposition-to-evidence binding.

    The semantic pack digest is the existing contract for this binding. Keep a
    named wrapper here so recovery progress does not conflate it with raw
    evidence or slot-state progress.
    """

    if request is None or bundle is None:
        return ""
    from ktem.reasoning.mara_semantic_proposition_packing import (
        pack_semantic_proposition_evidence,
        required_semantic_proposition_slots,
        semantic_proposition_pack_digest,
    )

    from .query_planning import request_planning_question
    from .question_proposition import build_question_proposition

    slots = required_semantic_proposition_slots(request)
    if not slots:
        return ""
    question = request_planning_question(request)
    packing = pack_semantic_proposition_evidence(request, question, slots, bundle)
    aliases = _progress_aliases(bundle)
    canonical_records = sorted(
        (_canonical_binding_record(record, aliases) for record in packing.records),
        key=lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")),
    )
    return semantic_proposition_pack_digest(
        build_question_proposition(question),
        _canonical_binding_slots(slots, aliases),
        canonical_records,
        item_char_limit=packing.item_char_limit,
    )


def semantic_raw_evidence_digest(bundle: EvidenceBundle | None) -> str:
    if bundle is None:
        return ""
    records = sorted(
        (_canonical_evidence_record(item) for item in bundle.items),
        key=lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")),
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
    slot_states: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    aliases = _progress_aliases(bundle)
    normalized = [
        {
            "slot_id": str(state.get("slot_id") or ""),
            "status": str(state.get("status") or "missing"),
            "evidence_ids": sorted(
                {
                    aliases.get(
                        str(evidence_id),
                        _RUNTIME_UUID_RE.sub("<runtime-uuid>", str(evidence_id)),
                    )
                    for evidence_id in state.get("evidence_ids") or []
                    if str(evidence_id)
                }
            ),
        }
        for state in slot_states or []
    ]
    return sorted(normalized, key=lambda state: state["slot_id"])


def normalized_slot_state_digest(
    bundle: EvidenceBundle | None,
    slot_states: list[dict[str, Any]] | None,
) -> str:
    """Digest required slot state after UUID-independent normalization."""

    if bundle is None or not slot_states:
        return ""
    normalized = semantic_progress_slot_states(bundle, slot_states)
    if not normalized or any(not state["slot_id"] for state in normalized):
        return ""
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def semantic_recovery_has_progress(
    initial_bundle: EvidenceBundle | None,
    recovered_bundle: EvidenceBundle | None,
    before_slots: list[dict[str, Any]] | None,
    after_slots: list[dict[str, Any]] | None,
    *,
    request: Any | None = None,
) -> bool:
    evidence_before = semantic_raw_evidence_digest(initial_bundle)
    evidence_after = semantic_raw_evidence_digest(recovered_bundle)
    slot_before = normalized_slot_state_digest(initial_bundle, before_slots)
    slot_after = normalized_slot_state_digest(recovered_bundle, after_slots)
    binding_before = canonical_proposition_binding_digest(request, initial_bundle)
    binding_after = canonical_proposition_binding_digest(request, recovered_bundle)
    return (
        bool(evidence_before and evidence_after and evidence_before != evidence_after)
        or bool(slot_before and slot_after and slot_before != slot_after)
        or bool(binding_before and binding_after and binding_before != binding_after)
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
        return _RUNTIME_UUID_RE.sub("<runtime-uuid>", semantic)
    payload = _canonical_evidence_record(item)
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"retrieval-semantic-fallback:{digest}"


def _canonical_evidence_record(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    return {
        "semantic_identity": _RUNTIME_UUID_RE.sub(
            "<runtime-uuid>", semantic_retrieval_identity(item) or ""
        ),
        "document_id": _stable_text_value(
            item,
            nested,
            "evaluation_source_id",
            "canonical_document_id",
            "canonical_dataset_id",
            "document_id",
        ),
        "page_label": _stable_text_value(
            item,
            nested,
            "page_label",
            "page_number",
            "page",
            "page_idx",
        ),
        "section_id": _stable_text_value(item, nested, "section_id"),
        "span_id": _stable_locator_value(item, nested, "span_id"),
        "element_id": _stable_locator_value(item, nested, "element_id"),
        "canonical_start": item.get("canonical_start"),
        "canonical_end": item.get("canonical_end"),
        "chunk_start": _first_value(item, nested, "chunk_start", "start_char"),
        "chunk_end": _first_value(item, nested, "chunk_end", "end_char"),
        "modality": _stable_text_value(item, nested, "modality") or "text",
        "text": _normalized_text(evidence_item_text(item)),
    }


def _canonical_binding_slots(
    slots: list[dict[str, Any]], aliases: dict[str, str]
) -> list[dict[str, Any]]:
    return [
        {
            **slot,
            "evidence_ids": _canonical_binding_values(
                slot.get("evidence_ids") or [], aliases
            ),
            "evidence_refs": _canonical_binding_values(
                slot.get("evidence_refs") or [], aliases
            ),
        }
        for slot in slots
    ]


def _canonical_binding_record(
    record: dict[str, Any], aliases: dict[str, str]
) -> dict[str, Any]:
    output = dict(record)
    evidence_id = str(record.get("evidence_id") or "")
    output["evidence_id"] = aliases.get(
        evidence_id,
        _RUNTIME_UUID_RE.sub("<runtime-uuid>", evidence_id),
    )
    for key in ("semantic_identity", "source_id"):
        output[key] = _RUNTIME_UUID_RE.sub("<runtime-uuid>", str(record.get(key) or ""))
    output["evidence_refs"] = _canonical_binding_values(
        record.get("evidence_refs") or [], aliases
    )
    return output


def _canonical_binding_values(values: Any, aliases: dict[str, str]) -> list[str]:
    return list(
        dict.fromkeys(
            aliases.get(
                str(value).strip(),
                _RUNTIME_UUID_RE.sub("<runtime-uuid>", str(value).strip()),
            )
            for value in values
            if str(value).strip()
        )
    )


def _stable_text_value(
    item: dict[str, Any],
    metadata: dict[str, Any],
    *keys: str,
) -> str:
    for key in keys:
        for container in (item, metadata):
            value = str(container.get(key) or "").strip()
            if value:
                normalized = _RUNTIME_UUID_RE.sub("<runtime-uuid>", value)
                if normalized != "<runtime-uuid>":
                    return normalized
    return ""


def _stable_locator_value(
    item: dict[str, Any],
    metadata: dict[str, Any],
    key: str,
) -> str:
    for container in (item, metadata):
        value = str(container.get(key) or "").strip()
        if value:
            return _RUNTIME_UUID_RE.sub("<runtime-uuid>", value)
    return ""


def _first_value(item: dict[str, Any], metadata: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        for container in (item, metadata):
            value = container.get(key)
            if value not in (None, ""):
                return value
    return None


def _normalized_text(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())
