from __future__ import annotations

import hashlib
from typing import Any

from ktem.docqa.boolean_evidence_scope import evidence_item_text
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_phrase_extraction import source_page_locator
from ktem.docqa.retrieval_semantic_identity import semantic_retrieval_identity

from .mara_qasper_candidate_selector_semantics import evidence_polarity_priority
from .mara_semantic_candidate_priority import (
    candidate_source_fields,
    semantic_record_priority,
)
from .mara_semantic_proposition_packing_support import (
    evidence_alignment_score,
    evidence_refs,
    matching_slot_ids,
    optional_int,
    ranked_evidence_positions,
    stable_source_id,
)

_RankedSourceRecordsTrace = tuple[
    list[tuple[tuple[int | float, ...], dict[str, Any]]],
    list[dict[str, Any]],
]


def ranked_source_records(
    request: Any,
    question: str,
    slots: list[dict[str, str]],
    bundle: EvidenceBundle,
    *,
    candidate_priority: bool,
) -> list[tuple[tuple[int | float, ...], dict[str, Any]]]:
    records, _decisions = ranked_source_records_with_trace(
        request,
        question,
        slots,
        bundle,
        candidate_priority=candidate_priority,
    )
    return records


def ranked_source_records_with_trace(
    request: Any,
    question: str,
    slots: list[dict[str, str]],
    bundle: EvidenceBundle,
    *,
    candidate_priority: bool,
) -> _RankedSourceRecordsTrace:
    preferred = _preferred_evidence_ids(request)
    ranked_positions = ranked_evidence_positions(bundle)
    records: list[tuple[tuple[int | float, ...], dict[str, Any]]] = []
    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(bundle.items):
        text = evidence_item_text(item)
        text_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        try:
            identity = identity_of(item)
        except ValueError:
            _append_rejection(
                decisions,
                index,
                text_digest=text_digest,
                text_chars=len(text),
                reason="source_identity_invalid",
            )
            continue
        evidence_id = identity.key
        if not text.strip():
            _append_rejection(
                decisions,
                index,
                evidence_id=evidence_id,
                text_digest=text_digest,
                text_chars=len(text),
                reason="empty_source_text",
            )
            continue
        if evidence_id in seen:
            _append_rejection(
                decisions,
                index,
                evidence_id=evidence_id,
                text_digest=text_digest,
                text_chars=len(text),
                reason="duplicate_evidence_id",
            )
            continue
        seen.add(evidence_id)
        priority, source_record = _rank_source_record(
            request,
            question,
            slots,
            item,
            identity=identity,
            evidence_id=evidence_id,
            text=text,
            index=index,
            preferred=preferred,
            ranked_positions=ranked_positions,
            candidate_priority=candidate_priority,
        )
        records.append((priority, source_record))
        decisions.append(
            _raw_source_decision(
                index,
                evidence_id=evidence_id,
                text_digest=text_digest,
                text_chars=len(text),
                decision="eligible",
                reason="accepted_for_semantic_ranking",
            )
        )
    return records, decisions


def _rank_source_record(
    request: Any,
    question: str,
    slots: list[dict[str, str]],
    item: Any,
    *,
    identity: Any,
    evidence_id: str,
    text: str,
    index: int,
    preferred: set[str],
    ranked_positions: dict[str, int],
    candidate_priority: bool,
) -> tuple[tuple[int | float, ...], dict[str, Any]]:
    source_id, page_label = source_page_locator(item)
    required_slot_ids = matching_slot_ids(slots, evidence_id)
    alignment_score = evidence_alignment_score(request, question, item)
    priority = semantic_record_priority(
        question,
        text,
        candidate_priority=candidate_priority,
        polarity_priority=evidence_polarity_priority(question, text),
        alignment_score=alignment_score,
        slot_priority=0 if evidence_id in preferred or required_slot_ids else 1,
        ranked_position=ranked_positions.get(
            evidence_id, len(ranked_positions) + index
        ),
    )
    return priority, _source_record(
        item,
        identity=identity,
        text=text,
        source_id=source_id,
        page_label=page_label,
        required_slot_ids=required_slot_ids,
        alignment_score=alignment_score,
        candidate_priority=candidate_priority,
    )


def _append_rejection(
    decisions: list[dict[str, Any]],
    index: int,
    *,
    text_digest: str,
    text_chars: int,
    reason: str,
    evidence_id: str = "",
) -> None:
    decisions.append(
        _raw_source_decision(
            index,
            evidence_id=evidence_id,
            text_digest=text_digest,
            text_chars=text_chars,
            decision="rejected",
            reason=reason,
        )
    )


def source_record_decisions(
    raw_decisions: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Close each raw source decision at its final packing boundary."""

    by_evidence_id = {
        str(observation.get("evidence_id") or ""): observation
        for observation in observations
        if str(observation.get("evidence_id") or "")
    }
    output: list[dict[str, Any]] = []
    for raw in raw_decisions:
        evidence_id = str(raw.get("evidence_id") or "")
        observation = by_evidence_id.get(evidence_id)
        if observation is None or raw.get("decision") != "eligible":
            output.append(dict(raw))
            continue
        stop_stage = str(observation.get("stop_stage") or "")
        output.append(
            {
                **raw,
                "semantic_rank": observation.get("semantic_rank"),
                "priority": list(observation.get("priority") or []),
                "selected_for_windowing": observation.get("selected_for_windowing")
                is True,
                "packed": observation.get("packed") is True,
                "decision": "packed"
                if observation.get("packed") is True
                else "rejected",
                "reason": stop_stage or "source_record_unresolved",
            }
        )
    return output


def _raw_source_decision(
    index: int,
    *,
    text_digest: str,
    text_chars: int,
    decision: str,
    reason: str,
    evidence_id: str = "",
) -> dict[str, Any]:
    return {
        "source_item_index": index + 1,
        "evidence_id": evidence_id,
        "text_digest": text_digest,
        "text_chars": text_chars,
        "decision": decision,
        "reason": reason,
    }


def selected_source_records(
    records: list[tuple[tuple[int | float, ...], dict[str, Any]]],
    *,
    max_items: int,
) -> list[dict[str, Any]]:
    ranked = sorted(records, key=lambda row: (row[0], row[1]["evidence_id"]))
    return [value for _priority, value in ranked[:max_items]]


def dropped_source_record_count(
    source_records: list[dict[str, Any]],
    packed_records: list[dict[str, Any]],
) -> int:
    source_ids = {
        str(record.get("evidence_id") or "")
        for record in source_records
        if str(record.get("evidence_id") or "")
    }
    packed_ids = {
        str(record.get("evidence_id") or "")
        for record in packed_records
        if str(record.get("evidence_id") or "")
    }
    return len(source_ids - packed_ids)


def source_record_observations(
    ranked_records: list[tuple[tuple[int | float, ...], dict[str, Any]]],
    selected_records: list[dict[str, Any]],
    packed_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected_ids = {str(record.get("evidence_id") or "") for record in selected_records}
    packed_ids = {str(record.get("evidence_id") or "") for record in packed_records}
    observations: list[dict[str, Any]] = []
    ordered = sorted(ranked_records, key=lambda row: (row[0], row[1]["evidence_id"]))
    for rank, (priority, record) in enumerate(ordered, start=1):
        evidence_id = str(record.get("evidence_id") or "")
        text = str(record.get("text") or "")
        selected = evidence_id in selected_ids
        packed = evidence_id in packed_ids
        observations.append(
            {
                "evidence_id": evidence_id,
                "semantic_identity": str(record.get("semantic_identity") or ""),
                "source_id": str(record.get("source_id") or ""),
                "page_label": record.get("page_label"),
                "section_id": str(record.get("section_id") or ""),
                "canonical_start": record.get("canonical_start"),
                "text_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text_chars": len(text),
                "semantic_rank": rank,
                "priority": list(priority),
                "selected_for_windowing": selected,
                "packed": packed,
                "stop_stage": (
                    "packed"
                    if packed
                    else "fit_to_input_budget"
                    if selected
                    else "bounded_source_selection"
                ),
            }
        )
    return observations


def _source_record(
    item: Any,
    *,
    identity: Any,
    text: str,
    source_id: str,
    page_label: str,
    required_slot_ids: tuple[str, ...],
    alignment_score: float,
    candidate_priority: bool,
) -> dict[str, Any]:
    stable_id = stable_source_id(item) or source_id or identity.source_id
    evidence_id = identity.key
    return {
        "evidence_id": evidence_id,
        "semantic_identity": semantic_retrieval_identity(item) or evidence_id,
        "source_id": stable_id,
        "page_label": page_label,
        "section_id": str(item.get("section_id") or "").strip(),
        "canonical_start": optional_int(item.get("canonical_start")),
        "evidence_refs": list(evidence_refs(item)),
        "required_slot_ids": list(required_slot_ids),
        "proposition_alignment_score": alignment_score,
        "text": text,
        **candidate_source_fields(text, enabled=candidate_priority),
    }


def _preferred_evidence_ids(request: Any) -> set[str]:
    plan = getattr(request, "query_plan", None)
    raw_slots = (
        plan.get("evidence_slots", [])
        if isinstance(plan, dict)
        else getattr(plan, "evidence_slots", ()) or ()
    )
    return {
        str(evidence_id).strip()
        for slot in raw_slots
        for evidence_id in (
            slot.get("evidence_ids", [])
            if isinstance(slot, dict)
            else getattr(slot, "evidence_ids", ()) or ()
        )
        if str(evidence_id).strip()
    }
