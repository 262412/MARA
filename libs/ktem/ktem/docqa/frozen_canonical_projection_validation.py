from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from .canonical_proposition_evidence_plan_contract import canonical_plan_digest
from .frozen_canonical_projection_utils import (
    frozen_slot_evidence_ref_valid,
    nonempty_string,
    slot_refs,
    string_tuple,
    token_tuple,
)
from .qasper_semantic_pack_contract import canonical_payload_digest
from .question_proposition import PROPOSITION_EVIDENCE_SLOTS, QuestionProposition


def selector_lookup(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]] | None:
    output: dict[str, dict[str, Any]] = {}
    for record in records:
        evidence_id = nonempty_string(record.get("evidence_id"))
        if not evidence_id:
            return None
        selectors = record.get("selectors")
        if not isinstance(selectors, list):
            return None
        for selector in selectors:
            if not isinstance(selector, Mapping):
                return None
            selector_id = nonempty_string(selector.get("selector_id"))
            if not selector_id or selector_id in output:
                return None
            output[selector_id] = {"evidence_id": evidence_id, **dict(selector)}
    return output


def selector_projection_reason(
    selector: Mapping[str, Any],
    *,
    evidence_id: str,
    selector_id: str,
    expected_relation: str,
    expected_required_tokens: tuple[str, ...],
    expected_slots: tuple[str, ...],
    proposition: QuestionProposition | None,
) -> str:
    header_reason = _selector_header_reason(selector, expected_slots)
    if header_reason:
        return header_reason
    alignment_reason = _alignment_reason(
        selector,
        evidence_id=evidence_id,
        selector_id=selector_id,
        expected_required_tokens=expected_required_tokens,
        expected_slots=expected_slots,
        proposition=proposition,
    )
    if alignment_reason:
        return alignment_reason
    raw_slots = selector.get("proposition_slot_spans")
    if not isinstance(raw_slots, Mapping) or set(raw_slots) != set(expected_slots):
        return "canonical_plan_projection_slot_span_invalid"
    text = str(selector.get("text") or "")
    start = selector.get("span_start")
    end = selector.get("span_end")
    parent_digest = canonical_payload_digest(text)
    for slot in expected_slots:
        reason = _slot_span_reason(
            raw_slots.get(slot),
            selector_id=selector_id,
            slot=slot,
            text=text,
            start=start,
            end=end,
            parent_digest=parent_digest,
        )
        if reason:
            return reason
    return ""


def _selector_header_reason(
    selector: Mapping[str, Any],
    expected_slots: tuple[str, ...],
) -> str:
    text = str(selector.get("text") or "")
    start = selector.get("span_start")
    end = selector.get("span_end")
    allowed = selector.get("allowed_proposition_slots")
    if (
        not text
        or not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
        or start < 0
        or end <= start
        or end - start != len(text)
        or not isinstance(allowed, list)
        or tuple(allowed) != expected_slots
        or selector.get("relation_bearing") is not True
        or selector.get("assertion_scope") != "asserted"
        or str(selector.get("candidate_relation_role") or "") != "polarity_evidence"
    ):
        return "canonical_plan_projection_selector_invalid"
    return ""


def _alignment_reason(
    selector: Mapping[str, Any],
    *,
    evidence_id: str,
    selector_id: str,
    expected_required_tokens: tuple[str, ...],
    expected_slots: tuple[str, ...],
    proposition: QuestionProposition | None,
) -> str:
    alignment = selector.get("semantic_alignment")
    if not isinstance(alignment, Mapping):
        return "canonical_plan_projection_alignment_invalid"
    alignment_payload = deepcopy(dict(alignment))
    alignment_digest = nonempty_string(alignment_payload.pop("alignment_digest", ""))
    covered = token_tuple(alignment.get("covered_object_tokens"))
    observed_refs = (
        {str(slot): str(ref) for slot, ref in alignment.get("slot_refs", {}).items()}
        if isinstance(alignment.get("slot_refs"), Mapping)
        else {}
    )
    if (
        alignment.get("contract_id") != "qasper_selector_semantic_alignment.v1"
        or alignment.get("status") != "verified"
        or alignment_digest != canonical_payload_digest(alignment_payload)
        or alignment.get("selector_id") != selector_id
        or alignment.get("evidence_id") != evidence_id
        or alignment.get("event_id") != selector.get("event_id")
        or alignment.get("span_start") != selector.get("span_start")
        or alignment.get("span_end") != selector.get("span_end")
        or alignment.get("text_digest")
        != canonical_payload_digest(str(selector.get("text") or ""))
        or alignment.get("polarity_relation")
        not in {"proposition_support", "explicit_contradiction", "undetermined"}
        or token_tuple(alignment.get("required_object_tokens"))
        != expected_required_tokens
        or not set(covered) <= set(expected_required_tokens)
        or observed_refs != {slot: selector_id for slot in expected_slots}
    ):
        return "canonical_plan_projection_alignment_invalid"
    if (
        proposition is not None
        and alignment.get("proposition_id") != proposition.proposition_id
    ):
        return "canonical_plan_projection_alignment_invalid"
    return ""


def _slot_span_reason(
    child: Any,
    *,
    selector_id: str,
    slot: str,
    text: str,
    start: Any,
    end: Any,
    parent_digest: str,
) -> str:
    if not isinstance(child, Mapping):
        return "canonical_plan_projection_slot_span_invalid"
    child_text = str(child.get("text") or "")
    child_start = child.get("span_start")
    child_end = child.get("span_end")
    clause_ref = child.get("clause_ref")
    clause_start = child.get("clause_start", start)
    clause_end = child.get("clause_end", end)
    if (
        not child_text
        or not isinstance(child_start, int)
        or isinstance(child_start, bool)
        or not isinstance(child_end, int)
        or isinstance(child_end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or child_start < start
        or child_end > end
        or child_end <= child_start
        or child_end - child_start != len(child_text)
        or not isinstance(clause_ref, str)
        or not clause_ref.strip()
        or text[child_start - start : child_end - start] != child_text
        or child.get("parent_selector_id") != selector_id
        or child.get("parent_span_start") != start
        or child.get("parent_span_end") != end
        or child.get("parent_text_digest") != parent_digest
        or child.get("text_digest") != canonical_payload_digest(child_text)
        or not frozen_slot_evidence_ref_valid(
            child.get("evidence_ref"),
            selector_id=selector_id,
            slot=slot,
            span_start=child_start,
            span_end=child_end,
        )
    ):
        return "canonical_plan_projection_slot_span_invalid"
    if (
        not isinstance(clause_start, int)
        or isinstance(clause_start, bool)
        or not isinstance(clause_end, int)
        or isinstance(clause_end, bool)
        or clause_start < start
        or clause_end > end
        or clause_end <= clause_start
    ):
        return "canonical_plan_projection_slot_span_invalid"
    return ""


def event_subplans(
    value: Any,
    *,
    span_refs: tuple[str, ...],
    slot_refs: dict[str, tuple[str, ...]],
    required_tokens: tuple[str, ...],
    covered_tokens: tuple[str, ...],
    event_id_by_ref: Mapping[str, str],
    proposition: QuestionProposition | None,
) -> tuple[tuple[dict[str, Any], ...], str]:
    if not isinstance(value, list) or not value:
        return (), "canonical_plan_projection_event_invalid"
    selected: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    seen_slots: dict[str, set[str]] = {slot: set() for slot in slot_refs}
    seen_event_ids: set[str] = set()
    seen_required_tokens: set[str] = set()
    seen_tokens: set[str] = set()
    for raw in value:
        parsed, reason = _event_subplan_values(
            raw,
            span_refs=span_refs,
            slot_refs=slot_refs,
            required_tokens=required_tokens,
            covered_tokens=covered_tokens,
            event_id_by_ref=event_id_by_ref,
            seen_event_ids=seen_event_ids,
        )
        if parsed is None:
            return (), reason or "canonical_plan_projection_event_invalid"
        event_id, refs, raw_slots, raw_required, raw_covered = parsed
        seen_refs.update(refs)
        seen_event_ids.add(event_id)
        seen_required_tokens.update(raw_required)
        for slot, refs_for_slot in raw_slots.items():
            seen_slots.setdefault(slot, set()).update(refs_for_slot)
        seen_tokens.update(raw_covered)
        selected.append(deepcopy(dict(raw)))
    if (
        seen_refs != set(span_refs)
        or any(
            seen_slots.get(slot, set()) != set(refs) for slot, refs in slot_refs.items()
        )
        or seen_required_tokens != set(required_tokens)
        or seen_tokens != set(covered_tokens)
    ):
        return (), "canonical_plan_projection_event_invalid"
    if proposition is not None:
        for raw in selected:
            if _event_binding_reason(raw, proposition):
                return (), "canonical_plan_projection_event_invalid"
    return tuple(selected), ""


def _event_subplan_values(
    raw: Any,
    *,
    span_refs: tuple[str, ...],
    slot_refs: dict[str, tuple[str, ...]],
    required_tokens: tuple[str, ...],
    covered_tokens: tuple[str, ...],
    event_id_by_ref: Mapping[str, str],
    seen_event_ids: set[str],
) -> tuple[
    tuple[
        str,
        tuple[str, ...],
        dict[str, tuple[str, ...]],
        tuple[str, ...],
        tuple[str, ...],
    ]
    | None,
    str,
]:
    if not isinstance(raw, Mapping):
        return None, "canonical_plan_projection_event_invalid"
    event_id = nonempty_string(raw.get("event_id"))
    event_binding_id = nonempty_string(raw.get("event_binding_id"))
    refs = string_tuple(raw.get("span_refs"))
    raw_slots = slot_refs_for_event(raw.get("slot_refs"), span_refs)
    if raw_slots is None:
        return None, "canonical_plan_projection_event_invalid"
    raw_required_values = string_tuple(raw.get("required_object_tokens"))
    raw_covered_values = string_tuple(raw.get("covered_object_tokens"))
    raw_required = token_tuple(raw_required_values)
    raw_covered = token_tuple(raw_covered_values)
    raw_slot_sets = {
        slot: set(refs_for_slot) for slot, refs_for_slot in raw_slots.items()
    }
    own_event_ids = {event_id_by_ref.get(ref, "") for ref in refs}
    expected_slots = {
        slot: set(refs).intersection(slot_refs[slot])
        for slot in slot_refs
        if set(refs).intersection(slot_refs[slot])
    }
    invalid = (
        raw.get("contract_id") != "canonical_event_proposition_plan.v1"
        or not event_id
        or not event_binding_id
        or not refs
        or len(set(refs)) != len(refs)
        or not set(refs) <= set(span_refs)
        or own_event_ids != {event_id}
        or event_id in seen_event_ids
        or set(raw_slots) != set(expected_slots)
        or any(
            set(raw_slots.get(slot, ())) != refs_for_slot
            for slot, refs_for_slot in expected_slots.items()
        )
        or not raw_required
        or len(raw_required) != len(raw_required_values)
        or len(raw_covered) != len(raw_covered_values)
        or not raw_covered
        or set(raw_covered) != set(raw_required)
        or not set(raw_required) <= set(required_tokens)
        or not set(raw_covered) <= set(covered_tokens)
        or any(
            slot not in slot_refs or not refs_for_slot <= set(slot_refs[slot])
            for slot, refs_for_slot in raw_slot_sets.items()
        )
    )
    if invalid:
        return None, "canonical_plan_projection_event_invalid"
    return (event_id, refs, raw_slots, raw_required, raw_covered), ""


def slot_refs_for_event(
    value: Any,
    span_refs: tuple[str, ...],
) -> dict[str, tuple[str, ...]] | None:
    return slot_refs(value, span_refs)


def _event_binding_reason(
    raw: Mapping[str, Any],
    proposition: QuestionProposition,
) -> str:
    expected = canonical_plan_digest(
        {
            "proposition_id": proposition.proposition_id,
            "event_id": raw["event_id"],
            "span_refs": tuple(raw["span_refs"]),
            "slot_refs": tuple(
                (slot, tuple(raw["slot_refs"][slot]))
                for slot in PROPOSITION_EVIDENCE_SLOTS
                if slot in raw["slot_refs"]
            ),
        }
    )
    return "" if raw["event_binding_id"] == expected else "mismatch"


def comparison_relation_reason(
    value: Any,
    *,
    event_subplans: Sequence[Mapping[str, Any]],
    polarity_relation: str,
) -> str:
    if len(event_subplans) <= 1:
        return (
            "canonical_plan_projection_comparison_invalid" if value is not None else ""
        )
    if polarity_relation != "explicit_contradiction" or not isinstance(value, Mapping):
        return "canonical_plan_projection_comparison_invalid"
    if value.get("contract_id") != "canonical_event_comparison_relation.v1":
        return "canonical_plan_projection_comparison_invalid"
    if value.get("relation_type") not in {"partial_scope", "role_incompatibility"}:
        return "canonical_plan_projection_comparison_invalid"
    event_bindings = {
        str(item.get("event_binding_id") or "") for item in event_subplans
    }
    if (
        str(value.get("contradicting_event_binding_id") or "") not in event_bindings
        or str(value.get("reference_event_binding_id") or "") not in event_bindings
        or value.get("contradicting_event_binding_id")
        == value.get("reference_event_binding_id")
    ):
        return "canonical_plan_projection_comparison_invalid"
    return ""
