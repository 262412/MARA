from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .question_proposition import PROPOSITION_EVIDENCE_SLOTS


def frozen_slot_support_by_ref(
    span_refs: Sequence[str],
    slots: Sequence[Any],
) -> tuple[dict[str, tuple[str, ...]] | None, str]:
    """Project query-slot ownership from the frozen slot evidence refs."""

    refs = tuple(str(ref) for ref in span_refs if str(ref))
    required: dict[str, tuple[str, ...]] = {}
    for slot in slots:
        slot_id = str(
            slot.get("slot_id")
            if isinstance(slot, Mapping)
            else getattr(slot, "slot_id", "")
        ).strip()
        required_flag = (
            slot.get("required_for_verification", True)
            if isinstance(slot, Mapping)
            else getattr(slot, "required_for_verification", True)
        )
        if not required_flag:
            continue
        raw_evidence_refs = (
            slot.get("evidence_refs")
            if isinstance(slot, Mapping)
            else getattr(slot, "evidence_refs", ())
        )
        if not slot_id or not isinstance(raw_evidence_refs, (list, tuple)):
            return None, "canonical_plan_projection_slot_support_invalid"
        evidence_refs = tuple(
            dict.fromkeys(
                str(ref).strip() for ref in raw_evidence_refs if str(ref).strip()
            )
        )
        if not evidence_refs or slot_id in required:
            return None, "canonical_plan_projection_slot_support_invalid"
        required[slot_id] = evidence_refs
    if not refs or not required:
        return None, "canonical_plan_projection_slot_support_invalid"
    plan_ref_set = set(refs)
    if any(set(evidence_refs) - plan_ref_set for evidence_refs in required.values()):
        return None, "canonical_plan_projection_slot_support_invalid"
    support_by_ref = {
        ref: tuple(
            sorted(
                slot_id
                for slot_id, evidence_refs in required.items()
                if ref in evidence_refs
            )
        )
        for ref in refs
    }
    if any(not support for support in support_by_ref.values()) or any(
        not any(slot_id in support for support in support_by_ref.values())
        for slot_id in required
    ):
        return None, "canonical_plan_projection_slot_support_invalid"
    return support_by_ref, ""


def slot_refs(
    value: Any,
    span_refs: tuple[str, ...],
) -> dict[str, tuple[str, ...]] | None:
    if not isinstance(value, Mapping):
        return None
    result: dict[str, tuple[str, ...]] = {}
    for raw_slot, raw_refs in value.items():
        slot = str(raw_slot or "")
        refs = string_tuple(raw_refs)
        if (
            slot not in PROPOSITION_EVIDENCE_SLOTS
            or not refs
            or len(set(refs)) != len(refs)
            or not set(refs) <= set(span_refs)
        ):
            return None
        result[slot] = refs
    return result


def string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item) for item in value if str(item))


def token_tuple(value: Any) -> tuple[str, ...]:
    return tuple(sorted(set(string_tuple(value))))


def proof_mode(value: Any, count: int) -> str | None:
    if value in {None, ""}:
        return "atomic_semantic" if count == 1 else "composite_conjunction"
    resolved = str(value)
    if resolved == "atomic_semantic" and count == 1:
        return resolved
    if resolved == "composite_conjunction" and 2 <= count <= 4:
        return resolved
    return None


def nonempty_string(value: Any) -> str:
    return str(value or "").strip()


def frozen_slot_evidence_ref_valid(
    value: Any,
    *,
    selector_id: str,
    slot: str,
    span_start: int,
    span_end: int,
) -> bool:
    reference = str(value or "")
    return bool(
        reference.startswith(f"{selector_id}#")
        and reference.endswith(f":{slot}:{span_start}:{span_end}")
    )
