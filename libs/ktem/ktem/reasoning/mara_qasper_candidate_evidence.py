from __future__ import annotations

from typing import Any

from ktem.docqa.canonical_proposition_evidence_plan import (
    canonical_proposition_evidence_selection,
)
from ktem.docqa.qasper_semantic_pack_contract import canonical_payload_digest

from .mara_qasper_candidate_evidence_projection import (
    exact_selector_valid as _exact_selector_valid,
)
from .mara_qasper_candidate_evidence_result import candidate_evidence_set_result
from .mara_qasper_candidate_plan_metadata import candidate_selector_plan_metadata
from .mara_qasper_candidate_relation import candidate_relation_anchor
from .mara_qasper_candidate_relation import (
    normalized_candidate_object_tokens as _normalized_object_tokens,
)
from .mara_qasper_candidate_selector_semantics import (
    applicable_candidate_slots as _applicable_candidate_slots,
)
from .mara_qasper_candidate_selector_semantics import (
    required_candidate_slots as _required_candidate_slots,
)
from .mara_qasper_candidate_selector_semantics import (
    revalidated_selector_semantics as _revalidated_selector_semantics,
)

_PROPOSITION_SLOTS = ("actor", "predicate", "object", "quantifier")


def candidate_selector_options(
    record: dict[str, Any],
    *,
    question: str = "",
) -> list[dict[str, Any]]:
    required_slots = set(_required_candidate_slots(question))
    options: list[dict[str, Any]] = []
    for selector in record.get("selectors") or []:
        if not isinstance(selector, dict) or not _exact_selector_valid(
            selector,
            record_text=record.get("text"),
            record_text_start=record.get("text_start"),
        ):
            continue
        selector_text = str(selector.get("text") or "")
        semantics = _revalidated_selector_semantics(
            selector,
            question,
            selector_text,
        )
        slot_hints = list(semantics["slots"])
        if (
            not slot_hints
            and semantics["candidate_relation_role"] != "uncertainty_context"
        ):
            continue
        locally_verified_slots = list(slot_hints)
        jointly_aligned = required_slots <= set(locally_verified_slots)
        options.append(
            {
                "evidence_id": str(record.get("evidence_id") or "").strip(),
                "evidence_ref": str(selector.get("selector_id") or ""),
                "span_start": selector.get("span_start"),
                "span_end": selector.get("span_end"),
                "text": selector_text,
                "slot_hints": slot_hints,
                "locally_verified_slots": locally_verified_slots,
                "allowed_proposition_slots": locally_verified_slots,
                "relation_bearing": bool(semantics["relation_bearing"]),
                "candidate_relation_role": str(semantics["candidate_relation_role"]),
                "local_relation_state": str(semantics["local_relation_state"]),
                "proposition_slot_spans": semantics["slot_spans"],
                "joint_slot_hint": jointly_aligned,
                "polarity_signal": (
                    str(semantics["polarity_signal"])
                    if jointly_aligned
                    else "undetermined"
                ),
            }
        )
    return sorted(
        options, key=lambda option: _selector_prompt_priority(question, option)
    )


def candidate_evidence_set_binding(
    records: list[dict[str, Any]] | dict[str, Any],
    question: str,
    *,
    candidate_transaction_id: str = "",
) -> dict[str, Any]:
    """Return bounded, retrieval-only exact-span evidence-set observations."""

    packed_records = [records] if isinstance(records, dict) else list(records)
    required_slots = _required_candidate_slots(question)
    applicable_slots = _applicable_candidate_slots(question)
    selectors = _revalidated_candidate_selectors(packed_records, question)
    selection = canonical_proposition_evidence_selection(
        question,
        selectors,
        required_slots,
        candidate_transaction_id=candidate_transaction_id,
    )
    result = candidate_evidence_set_result(
        packed_records,
        question,
        applicable_slots,
        selectors,
        selection.plan,
        selection.support,
        selection.contradiction,
    )
    result["binding_digest"] = canonical_payload_digest(result)
    return result


def _revalidated_candidate_selectors(
    records: list[dict[str, Any]],
    question: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for record in records:
        for selector in record.get("selectors") or []:
            if not isinstance(selector, dict) or not _exact_selector_valid(
                selector,
                record_text=record.get("text"),
                record_text_start=record.get("text_start"),
            ):
                continue
            text = str(selector.get("text") or "")
            semantics = _revalidated_selector_semantics(selector, question, text)
            output.append(
                {
                    "evidence_id": str(record.get("evidence_id") or "").strip(),
                    "selector_id": str(selector.get("selector_id") or "").strip(),
                    "text": text,
                    "span_start": selector.get("span_start"),
                    "span_end": selector.get("span_end"),
                    "slot_hints": list(semantics["slots"]),
                    "proposition_slot_spans": dict(semantics["slot_spans"]),
                    "relation_bearing": bool(semantics["relation_bearing"]),
                    "local_relation_state": str(semantics["local_relation_state"]),
                    **candidate_selector_plan_metadata(
                        record,
                        selector,
                        question,
                        semantics,
                    ),
                }
            )
    return output


def candidate_required_slots_from_binding(
    slots: list[dict[str, Any]],
    binding: dict[str, Any],
) -> list[dict[str, Any]]:
    """Project logical verification slots from one canonical proposition binding."""

    supplied_digest = str(binding.get("binding_digest") or "")
    digest_payload = {
        key: value for key, value in binding.items() if key != "binding_digest"
    }
    if (
        not supplied_digest
        or canonical_payload_digest(digest_payload) != supplied_digest
    ):
        raise ValueError("candidate_proposition_binding_digest_invalid")
    bound = binding.get("binding_state") in {
        "relation_bound_support",
        "relation_bound_contradiction",
    }
    evidence_ids = list(binding.get("evidence_ids") or []) if bound else []
    evidence_refs = list(binding.get("evidence_refs") or []) if bound else []
    polarity = str(binding.get("polarity_signal") or "undetermined")
    evidence_relation = {
        "support": "proposition_support",
        "explicit_contradiction": "explicit_contradiction",
    }.get(polarity, "undetermined")
    return [
        {
            "slot_id": str(slot.get("slot_id") or ""),
            "description": str(slot.get("description") or ""),
            "evidence_ids": list(evidence_ids),
            "evidence_refs": list(evidence_refs),
            "retrieved_evidence_ids": list(evidence_ids),
            "retrieved_evidence_refs": list(evidence_refs),
            "binding_status": "bound" if bound else "missing",
            "binding_reason": str(binding.get("binding_reason") or ""),
            "evidence_relation": evidence_relation,
            "typed_proposition": dict(binding.get("typed_proposition") or {}),
            "proposition_slot_evidence_refs": dict(
                binding.get("slot_evidence_refs") or {}
            ),
            "proposition_slot_spans": dict(binding.get("proposition_slot_spans") or {}),
            "proposition_slot_states": dict(binding.get("slot_states") or {}),
            "proposition_binding_digest": supplied_digest,
        }
        for slot in slots
    ]


def _selector_prompt_priority(
    question: str,
    option: dict[str, Any],
) -> tuple[int, int, int, int, int, int, str]:
    signal_priority = {
        "support": 0,
        "explicit_contradiction": 0,
        "undetermined": 1,
    }
    text = str(option.get("text") or "")
    overlap = len(_normalized_object_tokens(question) & _normalized_object_tokens(text))
    meta_only = int(text.lstrip().startswith("#"))
    return (
        signal_priority.get(str(option.get("polarity_signal") or ""), 1),
        0 if candidate_relation_anchor(question, text) else 1,
        -len(option.get("slot_hints") or []),
        meta_only,
        -overlap,
        int(option.get("span_start") or 0),
        str(option.get("evidence_ref") or ""),
    )


def candidate_selector_ids(record: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(selector.get("selector_id") or "").strip()
        for selector in record.get("selectors") or []
        if isinstance(selector, dict)
        and _exact_selector_valid(
            selector,
            record_text=record.get("text"),
            record_text_start=record.get("text_start"),
        )
    )


def exact_candidate_slot_binding(
    slot: dict[str, Any],
    records: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Return only a verified, all-slot, exact span binding from upstream state."""

    declared_refs = candidate_declared_refs(slot.get("evidence_refs"))
    declared_bindings = slot.get("proposition_slot_bindings")
    if not declared_refs or not isinstance(declared_bindings, dict):
        return [], []
    if len(declared_refs) > 4:
        return [], []
    if slot.get("binding_status") != "verified":
        return [], []
    if slot.get("evidence_relation") not in {
        "proposition_support",
        "explicit_contradiction",
    }:
        return [], []
    typed_proposition = slot.get("typed_proposition")
    if not isinstance(typed_proposition, dict):
        return [], []
    expected_bindings = {
        "actor": typed_proposition.get("actor"),
        "predicate": typed_proposition.get("predicate"),
        "object": typed_proposition.get("object_surface"),
        "quantifier": typed_proposition.get("quantifier"),
    }
    quantifier = " ".join(str(expected_bindings["quantifier"] or "").casefold().split())
    expected_binding_slots = set(_PROPOSITION_SLOTS)
    if quantifier in {"", "none"}:
        expected_binding_slots.remove("quantifier")
    if set(declared_bindings) != expected_binding_slots:
        return [], []
    if any(
        not str(declared_bindings[name] or "").strip()
        or " ".join(str(declared_bindings[name]).casefold().split())
        != " ".join(str(expected_bindings[name] or "").casefold().split())
        for name in expected_binding_slots
    ):
        return [], []
    if (
        _candidate_evidence_binding_refs(
            slot, declared_refs, declared_bindings, expected_bindings
        )
        is None
    ):
        return [], []
    ref_records = {
        selector_id: record
        for record in records
        for selector_id in candidate_selector_ids(record)
        if selector_id in declared_refs
    }
    if set(ref_records) != declared_refs:
        return [], []
    if any(
        not str(record.get("evidence_id") or "").strip()
        for record in ref_records.values()
    ):
        return [], []
    record_ids = list(
        dict.fromkeys(
            str(record.get("evidence_id") or "").strip()
            for record in ref_records.values()
        )
    )
    if not record_ids:
        return [], []
    return record_ids, sorted(declared_refs)


def _candidate_evidence_binding_refs(
    slot: dict[str, Any],
    declared_refs: set[str],
    declared_bindings: dict[str, Any],
    expected_bindings: dict[str, Any],
) -> dict[str, set[str]] | None:
    evidence_bindings = slot.get("proposition_slot_evidence_refs")
    if not isinstance(evidence_bindings, dict):
        return None
    quantifier = " ".join(str(expected_bindings["quantifier"] or "").casefold().split())
    expected_slots = set(declared_bindings)
    if quantifier in {"", "none"}:
        if "quantifier" in evidence_bindings and candidate_declared_refs(
            evidence_bindings.get("quantifier")
        ):
            return None
        expected_slots.discard("quantifier")
    if set(evidence_bindings) != expected_slots:
        return None
    per_slot_refs = {
        slot_name: candidate_declared_refs(evidence_bindings[slot_name])
        for slot_name in expected_slots
    }
    if any(not refs or not refs <= declared_refs for refs in per_slot_refs.values()):
        return None
    if set().union(*per_slot_refs.values()) != declared_refs:
        return None
    return per_slot_refs


def candidate_declared_refs(value: Any) -> set[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        return set()
    return {str(ref).strip() for ref in values if str(ref).strip()}
