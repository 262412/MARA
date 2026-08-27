from __future__ import annotations

from itertools import combinations
from typing import Any

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
    selector_direct_polarity_evidence as _selector_direct_polarity_evidence,
)
from .mara_qasper_candidate_selector_semantics import (
    selector_local_slots as _selector_local_slots,
)
from .mara_qasper_candidate_selector_semantics import (
    selector_polarity_signal as _selector_polarity_signal,
)
from .mara_qasper_candidate_selector_semantics import spans_overlap as _spans_overlap

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
        slot_hints = _selector_local_slots(selector, question, selector_text)
        locally_verified_slots = [
            str(slot)
            for slot in selector.get("allowed_proposition_slots", slot_hints)
            if str(slot) in _PROPOSITION_SLOTS
        ]
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
                "relation_bearing": bool(selector.get("relation_bearing", False)),
                "candidate_relation_role": str(
                    selector.get("candidate_relation_role") or ""
                ),
                "local_relation_state": str(selector.get("local_relation_state") or ""),
                "joint_slot_hint": jointly_aligned,
                "polarity_signal": (
                    _selector_polarity_signal(selector, question, selector_text)
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
    selectors = [
        {
            "evidence_id": str(record.get("evidence_id") or "").strip(),
            "selector_id": str(selector.get("selector_id") or "").strip(),
            "text": str(selector.get("text") or ""),
            "span_start": selector.get("span_start"),
            "span_end": selector.get("span_end"),
            "slot_hints": _selector_local_slots(
                selector,
                question,
                str(selector.get("text") or ""),
            ),
            "relation_bearing": bool(selector.get("relation_bearing", False)),
            "local_relation_state": str(selector.get("local_relation_state") or ""),
            "object_tokens": sorted(
                semantic_content_token_set(str(selector.get("text") or ""))
            ),
        }
        for record in packed_records
        for selector in record.get("selectors") or []
        if isinstance(selector, dict)
        and _exact_selector_valid(
            selector,
            record_text=record.get("text"),
            record_text_start=record.get("text_start"),
        )
    ]
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
    return _candidate_evidence_set_result(
        packed_records,
        question,
        applicable_slots,
        support,
        contradiction,
        complete,
    )


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
    relation_anchor_refs = [
        str(selector["selector_id"])
        for selector in selected or ()
        if "predicate" in selector.get("slot_hints", [])
    ]
    has_support = support is not None
    has_contradiction = contradiction is not None
    if has_support and not has_contradiction:
        polarity_signal = "support"
    elif has_contradiction and not has_support:
        polarity_signal = "explicit_contradiction"
    else:
        polarity_signal = "undetermined"
    selected_evidence_ids = list(
        dict.fromkeys(
            str(selector["evidence_id"])
            for selector in selected or ()
            if str(selector["evidence_id"])
        )
    )
    slot_states = {
        slot: (
            "not_applicable"
            if slot == "quantifier" and slot not in applicable_slots
            else "bound"
            if slot in selected_slots
            else "missing"
        )
        for slot in _PROPOSITION_SLOTS
    }
    return {
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
        "evidence_set_spans": _span_set_spans(selected),
        "slot_evidence_refs": selected_slots,
        "support": has_support,
        "support_evidence_refs": support_refs,
        "support_evidence_set_spans": _span_set_spans(support),
        "support_slot_evidence_refs": support_slots,
        "explicit_contradiction": has_contradiction,
        "explicit_contradiction_evidence_refs": contradiction_refs,
        "explicit_contradiction_evidence_set_spans": _span_set_spans(contradiction),
        "explicit_contradiction_slot_evidence_refs": contradiction_slots,
        "polarity_signal": polarity_signal,
        "relation_anchor_refs": relation_anchor_refs,
        "structural_features": _candidate_structural_features(
            question,
            selected,
            applicable_slots=applicable_slots,
        ),
    }


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


def _candidate_span_set(
    question: str,
    selectors: list[dict[str, Any]],
    required_slots: tuple[str, ...],
    *,
    polarity: str | None,
) -> tuple[dict[str, Any], ...] | None:
    ordered = sorted(selectors, key=_selector_sort_key)
    if polarity is None:
        pool = _bounded_selector_pool(ordered, required_slots, ())
        for count in range(1, min(4, len(pool)) + 1):
            for selected in combinations(pool, count):
                candidate = _valid_candidate_span_set(
                    question,
                    selected,
                    required_slots,
                    polarity=None,
                )
                if candidate is not None:
                    return candidate
        return None
    anchors = [
        selector
        for selector in ordered
        if "predicate" in selector.get("slot_hints", [])
        and _selector_polarity_signal(
            selector,
            question,
            str(selector["text"]),
        )
        == ("support" if polarity == "yes" else "explicit_contradiction")
    ]
    for anchor in anchors:
        pool = _bounded_selector_pool(ordered, required_slots, (anchor,))
        remaining = [selector for selector in pool if selector is not anchor]
        for count in range(0, min(3, len(remaining)) + 1):
            for extra in combinations(remaining, count):
                candidate = _valid_candidate_span_set(
                    question,
                    (anchor, *extra),
                    required_slots,
                    polarity=polarity,
                )
                if candidate is not None:
                    return candidate
    return None


def _selector_sort_key(value: dict[str, Any]) -> tuple[str, int, int, str]:
    return (
        str(value["evidence_id"]),
        int(value["span_start"]),
        int(value["span_end"]),
        str(value["selector_id"]),
    )


def _bounded_selector_pool(
    selectors: list[dict[str, Any]],
    required_slots: tuple[str, ...],
    anchors: tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    ranked = sorted(
        selectors,
        key=lambda value: (-len(value["slot_hints"]), _selector_sort_key(value)),
    )
    pool: list[dict[str, Any]] = []
    for selector in anchors:
        if selector not in pool:
            pool.append(selector)
    for slot in required_slots:
        for selector in ranked:
            if slot in selector["slot_hints"] and selector not in pool:
                pool.append(selector)
                break
    for selector in ranked:
        if selector not in pool:
            pool.append(selector)
    return pool


def _valid_candidate_span_set(
    question: str,
    selected: tuple[dict[str, Any], ...],
    required_slots: tuple[str, ...],
    *,
    polarity: str | None,
) -> tuple[dict[str, Any], ...] | None:
    ordered = tuple(sorted(selected, key=_selector_sort_key))
    if (
        any(
            not str(value["evidence_id"]).strip()
            or not str(value["selector_id"]).strip()
            for value in ordered
        )
        or len(
            {
                (str(value["evidence_id"]), str(value["selector_id"]))
                for value in ordered
            }
        )
        != len(ordered)
        or _spans_overlap(ordered)
    ):
        return None
    covered = {slot for value in ordered for slot in value["slot_hints"]}
    if not set(required_slots) <= covered:
        return None
    if not _object_coverage_sufficient(question, ordered):
        return None
    if not any("predicate" in value.get("slot_hints", []) for value in ordered):
        return None
    if not any(_selector_direct_polarity_evidence(value) for value in ordered):
        return None
    if polarity is not None and not _polarity_span_set_valid(
        question,
        ordered,
        required_slots,
        polarity=polarity,
    ):
        return None
    return ordered


def _object_coverage_sufficient(
    question: str,
    selected: tuple[dict[str, Any], ...],
) -> bool:
    required = semantic_content_token_set(
        build_question_proposition(question).object_surface
    )
    if not required:
        return False
    covered = {
        str(token)
        for selector in selected
        if "object" in selector.get("slot_hints", [])
        for token in selector.get("object_tokens") or []
        if str(token) in required
    }
    minimum = len(required) if len(required) <= 3 else (len(required) + 1) // 2
    return len(covered) >= minimum


def _polarity_span_set_valid(
    question: str,
    selected: tuple[dict[str, Any], ...],
    required_slots: tuple[str, ...],
    *,
    polarity: str,
) -> bool:
    anchors = [
        selector
        for selector in selected
        if "predicate" in selector.get("slot_hints", [])
        and _selector_polarity_signal(
            selector,
            question,
            str(selector["text"]),
        )
        == ("support" if polarity == "yes" else "explicit_contradiction")
    ]
    for anchor in anchors:
        same_record = all(
            selector["evidence_id"] == anchor["evidence_id"] for selector in selected
        )
        anchor_slots = set(anchor.get("slot_hints") or [])
        if same_record or set(required_slots) - {"actor"} <= anchor_slots:
            return True
    return False
