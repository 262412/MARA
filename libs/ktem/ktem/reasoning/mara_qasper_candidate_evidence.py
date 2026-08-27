from __future__ import annotations

from typing import Any

from ktem.docqa.qasper_boolean_no_evidence import qasper_no_evidence_set_analysis
from ktem.docqa.qasper_semantic_pack_contract import canonical_payload_digest
from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_lexical import semantic_content_token_set

from .mara_qasper_candidate_evidence_projection import (
    exact_selector_valid as _exact_selector_valid,
)
from .mara_qasper_candidate_evidence_projection import span_set_refs as _span_set_refs
from .mara_qasper_candidate_evidence_projection import (
    span_set_slot_refs as _span_set_slot_refs,
)
from .mara_qasper_candidate_evidence_projection import span_set_spans as _span_set_spans
from .mara_qasper_candidate_evidence_sets import (
    candidate_span_set as _candidate_span_set,
)
from .mara_qasper_candidate_evidence_sets import selector_sort_key as _selector_sort_key
from .mara_qasper_candidate_relation import candidate_relation_anchor
from .mara_qasper_candidate_relation import (
    normalized_candidate_object_tokens as _normalized_object_tokens,
)
from .mara_qasper_candidate_selector_semantics import (
    applicable_candidate_slots as _applicable_candidate_slots,
)
from .mara_qasper_candidate_selector_semantics import (
    candidate_structural_features as _candidate_structural_features,
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
) -> dict[str, Any]:
    """Return bounded, retrieval-only exact-span evidence-set observations."""

    packed_records = [records] if isinstance(records, dict) else list(records)
    required_slots = _required_candidate_slots(question)
    applicable_slots = _applicable_candidate_slots(question)
    selectors = _revalidated_candidate_selectors(packed_records, question)
    support = _candidate_span_set(
        question,
        selectors,
        required_slots,
        polarity="yes",
    )
    contradiction = _candidate_span_set(
        question,
        selectors,
        required_slots,
        polarity="no",
    )
    complete = (
        support
        or contradiction
        or _candidate_span_set(
            question,
            selectors,
            required_slots,
            polarity=None,
        )
    )
    result = _candidate_evidence_set_result(
        packed_records,
        question,
        applicable_slots,
        support,
        contradiction,
        complete,
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
                    "object_tokens": sorted(semantic_content_token_set(text)),
                }
            )
    return output


def _candidate_evidence_set_result(
    records: list[dict[str, Any]],
    question: str,
    applicable_slots: tuple[str, ...],
    support: tuple[dict[str, Any], ...] | None,
    contradiction: tuple[dict[str, Any], ...] | None,
    complete: tuple[dict[str, Any], ...] | None,
) -> dict[str, Any]:
    selected = support or contradiction or complete
    support_refs = _span_set_refs(support)
    contradiction_refs = _span_set_refs(contradiction)
    selected_refs = _span_set_refs(selected)
    support_slots = _span_set_slot_refs(support)
    contradiction_slots = _span_set_slot_refs(contradiction)
    selected_slots = _span_set_slot_refs(selected)
    selected_slot_spans = _span_set_slot_spans(selected)
    relation_anchor_refs = [
        str(selector["selector_id"])
        for selector in selected or ()
        if "predicate" in selector.get("slot_hints", [])
    ]
    has_support, has_contradiction, polarity_signal = _polarity_observation(
        support,
        contradiction,
    )
    selected_evidence_ids = _selected_evidence_ids(selected)
    slot_states = _candidate_slot_states(applicable_slots, selected_slots)
    no_semantics = qasper_no_evidence_set_analysis(question, contradiction or ())
    selector_universe_refs, selector_universe_status = _selector_universe(
        records,
        question,
        applicable_slots,
        support_refs,
        contradiction_refs,
        selected_refs,
    )
    return {
        "typed_proposition": build_question_proposition(question).as_dict(),
        "evidence_ids": selected_evidence_ids,
        "required_slots": list(applicable_slots),
        "applicable_slots": list(applicable_slots),
        "not_applicable_slots": [
            slot for slot in _PROPOSITION_SLOTS if slot not in applicable_slots
        ],
        "covered_slots": [
            slot for slot in _PROPOSITION_SLOTS if slot in selected_slots
        ],
        "slot_states": slot_states,
        "quantifier_evidence_state": slot_states["quantifier"],
        "binding_status": "bound" if complete is not None else "missing",
        "binding_reason": _candidate_binding_reason(records, complete),
        "evidence_refs": selected_refs,
        "selector_universe_refs": selector_universe_refs,
        "selector_universe_status": selector_universe_status,
        "evidence_set_spans": _span_set_spans(selected),
        "slot_evidence_refs": selected_slots,
        "proposition_slot_spans": selected_slot_spans,
        "support": has_support,
        "support_evidence_refs": support_refs,
        "support_evidence_set_spans": _span_set_spans(support),
        "support_slot_evidence_refs": support_slots,
        "explicit_contradiction": has_contradiction,
        "explicit_contradiction_evidence_refs": contradiction_refs,
        "explicit_contradiction_evidence_set_spans": _span_set_spans(contradiction),
        "explicit_contradiction_slot_evidence_refs": contradiction_slots,
        "no_evidence_semantics": no_semantics,
        "polarity_signal": polarity_signal,
        "relation_anchor_refs": relation_anchor_refs,
        "structural_features": _candidate_structural_features(
            question,
            selected,
            applicable_slots=applicable_slots,
        ),
    }


def _selected_evidence_ids(
    selected: tuple[dict[str, Any], ...] | None,
) -> list[str]:
    return list(
        dict.fromkeys(
            str(selector["evidence_id"])
            for selector in selected or ()
            if str(selector["evidence_id"])
        )
    )


def _candidate_slot_states(
    applicable_slots: tuple[str, ...],
    selected_slots: dict[str, list[str]],
) -> dict[str, str]:
    return {
        slot: (
            "not_applicable"
            if slot == "quantifier" and slot not in applicable_slots
            else "bound"
            if slot in selected_slots
            else "missing"
        )
        for slot in _PROPOSITION_SLOTS
    }


def _polarity_observation(
    support: tuple[dict[str, Any], ...] | None,
    contradiction: tuple[dict[str, Any], ...] | None,
) -> tuple[bool, bool, str]:
    has_support = support is not None
    has_contradiction = contradiction is not None
    if has_support and not has_contradiction:
        signal = "support"
    elif has_contradiction and not has_support:
        signal = "explicit_contradiction"
    else:
        signal = "undetermined"
    return has_support, has_contradiction, signal


def _selector_universe(
    records: list[dict[str, Any]],
    question: str,
    applicable_slots: tuple[str, ...],
    support_refs: list[str],
    contradiction_refs: list[str],
    selected_refs: list[str],
) -> tuple[list[str], str]:
    polarized = list(dict.fromkeys([*support_refs, *contradiction_refs]))
    if len(polarized) > 4:
        return [], "conflict_exceeds_four_spans"
    refs = (
        polarized
        or selected_refs
        or _relation_aligned_selector_refs(
            question,
            _revalidated_candidate_selectors(records, question),
            applicable_slots,
        )
    )
    return refs, "bounded"


def _span_set_slot_spans(
    selectors: tuple[dict[str, Any], ...] | None,
) -> dict[str, list[dict[str, Any]]]:
    return {
        slot: [
            dict(selector["proposition_slot_spans"][slot])
            for selector in selectors or ()
            if slot in dict(selector.get("proposition_slot_spans") or {})
        ]
        for slot in _PROPOSITION_SLOTS
        if any(
            slot in dict(selector.get("proposition_slot_spans") or {})
            for selector in selectors or ()
        )
    }


def _relation_aligned_selector_refs(
    question: str,
    selectors: list[dict[str, Any]],
    required_slots: tuple[str, ...],
) -> list[str]:
    required_object_tokens = semantic_content_token_set(
        build_question_proposition(question).object_surface
    )
    anchors = [
        selector
        for selector in selectors
        if "predicate" in selector.get("slot_hints", [])
        and selector.get("relation_bearing") is True
    ]
    anchors.sort(
        key=lambda selector: (
            -len(required_object_tokens & set(selector.get("object_tokens") or [])),
            -len(selector.get("slot_hints") or []),
            _selector_sort_key(selector),
        )
    )
    if not anchors:
        return []
    selected = anchors[:2]
    covered = {slot for value in selected for slot in value.get("slot_hints", [])}
    anchor_records = {str(value.get("evidence_id") or "") for value in selected}
    ranked = sorted(
        selectors,
        key=lambda selector: (
            -len(
                (set(required_slots) - covered) & set(selector.get("slot_hints") or [])
            ),
            -len(required_object_tokens & set(selector.get("object_tokens") or [])),
            _selector_sort_key(selector),
        ),
    )
    for selector in ranked:
        if selector in selected or len(selected) >= 4:
            continue
        slots = set(selector.get("slot_hints") or [])
        object_overlap = required_object_tokens & set(
            selector.get("object_tokens") or []
        )
        same_record = str(selector.get("evidence_id") or "") in anchor_records
        if slots - covered and (object_overlap or same_record):
            selected.append(selector)
            covered.update(slots)
    return [str(value["selector_id"]) for value in selected]


def _candidate_binding_reason(
    records: list[dict[str, Any]],
    complete: tuple[dict[str, Any], ...] | None,
) -> str:
    if complete is not None:
        return "exact_span_set"
    if any(
        str(record.get("evidence_id") or "").strip() or record.get("selectors")
        for record in records
    ):
        return "record_identity_only"
    return "no_exact_selectors"


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
    bound = binding.get("binding_status") == "bound"
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
