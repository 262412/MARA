from __future__ import annotations

import re
from itertools import combinations
from typing import Any

from ktem.docqa.boolean_evidence_scope import _actor
from ktem.docqa.boolean_proposition_polarity import evidence_polarity
from ktem.docqa.boolean_proposition_tokens import _content_tokens, _object_token
from ktem.docqa.question_proposition import build_question_proposition

from .mara_qasper_candidate_evidence_projection import (
    exact_selector_valid as _exact_selector_valid,
)
from .mara_qasper_candidate_evidence_projection import span_set_refs as _span_set_refs
from .mara_qasper_candidate_evidence_projection import (
    span_set_slot_refs as _span_set_slot_refs,
)
from .mara_qasper_candidate_evidence_projection import span_set_spans as _span_set_spans

_PROPOSITION_SLOTS = ("actor", "predicate", "object", "quantifier")
_NUMBER_EQUIVALENTS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


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
        slot_hints = candidate_slot_hints(question, selector_text)
        jointly_aligned = required_slots <= set(slot_hints)
        options.append(
            {
                "evidence_id": str(record.get("evidence_id") or "").strip(),
                "evidence_ref": str(selector.get("selector_id") or ""),
                "span_start": selector.get("span_start"),
                "span_end": selector.get("span_end"),
                "text": selector_text,
                "slot_hints": slot_hints,
                "joint_slot_hint": jointly_aligned,
                "polarity_signal": (
                    candidate_polarity_signal(question, selector_text)
                    if jointly_aligned
                    else "undetermined"
                ),
            }
        )
    signal_priority = {
        "support": 0,
        "explicit_contradiction": 0,
        "undetermined": 1,
    }
    return sorted(
        options,
        key=lambda option: signal_priority[str(option["polarity_signal"])],
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
            "slot_hints": candidate_slot_hints(
                question,
                str(selector.get("text") or ""),
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
        applicable_slots,
        support,
        contradiction,
        complete,
    )


def _candidate_evidence_set_result(
    records: list[dict[str, Any]],
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
        "binding_reason": (
            "exact_span_set"
            if complete is not None
            else "record_identity_only"
            if any(
                str(record.get("evidence_id") or "").strip() or record.get("selectors")
                for record in records
            )
            else "no_exact_selectors"
        ),
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
    }


def candidate_polarity_signal(question: str, text: str) -> str:
    if not set(_required_candidate_slots(question)) <= set(
        candidate_slot_hints(question, text)
    ):
        return "undetermined"
    observed = evidence_polarity(question, text, desired_polarity="yes")
    return {
        "yes": "support",
        "no": "explicit_contradiction",
    }.get(observed, "undetermined")


def evidence_polarity_priority(question: str, text: str) -> int:
    """Prefer explicit support or contradiction over unresolved text."""

    observed = candidate_polarity_signal(question, text)
    return 0 if observed in {"support", "explicit_contradiction"} else 1


def candidate_slot_hints(question: str, text: str) -> list[str]:
    """Return conservative, non-authoritative hints for one exact selector."""

    proposition = build_question_proposition(question)
    hints: list[str] = []
    if _candidate_actor_aligned(proposition.actor, proposition.subject_surface, text):
        hints.append("actor")
    if evidence_polarity(question, text, desired_polarity="yes") in {"yes", "no"}:
        hints.append("predicate")
    if _candidate_object_aligned(proposition.object_surface, text):
        hints.append("object")
    if _candidate_quantifier_aligned(proposition.quantifier, text):
        hints.append("quantifier")
    return hints


def _candidate_actor_aligned(actor: str, subject: str, text: str) -> bool:
    if actor == "current_paper":
        return _actor(text, "unknown") == "current_paper"
    if actor == "prior_work":
        return _actor(text, "related_work") == "cited_work"
    subject_tokens = _normalized_object_tokens(subject)
    return bool(subject_tokens and subject_tokens <= _normalized_object_tokens(text))


def _candidate_object_aligned(object_surface: str, text: str) -> bool:
    object_tokens = _normalized_object_tokens(object_surface)
    return bool(object_tokens and object_tokens <= _normalized_object_tokens(text))


def _normalized_object_tokens(value: str) -> set[str]:
    return {
        normalized
        for token in _content_tokens(value)
        if (normalized := _object_token(token))
    }


def _candidate_quantifier_aligned(quantifier: str, text: str) -> bool:
    normalized = " ".join(str(quantifier or "").casefold().split())
    if normalized in {"", "none"}:
        return False
    tokens = set(re.findall(r"[a-z0-9]+", str(text or "").casefold()))
    if normalized.startswith("count:"):
        count = normalized.partition(":")[2]
        equivalent = next(
            (word for word, value in _NUMBER_EQUIVALENTS.items() if value == count),
            None,
        )
        return bool(count in tokens or (equivalent and equivalent in tokens))
    equivalent = _NUMBER_EQUIVALENTS.get(normalized)
    if equivalent is not None:
        return normalized in tokens or equivalent in tokens
    reverse = {value: key for key, value in _NUMBER_EQUIVALENTS.items()}
    equivalent = reverse.get(normalized)
    if equivalent is not None:
        return normalized in tokens or equivalent in tokens
    return normalized in " ".join(str(text or "").casefold().split())


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


def _required_candidate_slots(question: str) -> tuple[str, ...]:
    return tuple(_applicable_candidate_slots(question))


def _applicable_candidate_slots(question: str) -> tuple[str, ...]:
    proposition = build_question_proposition(question)
    slots = list(_PROPOSITION_SLOTS[:-1])
    if " ".join(str(proposition.quantifier or "").casefold().split()) in {
        "",
        "none",
    }:
        return tuple(slots)
    slots.append("quantifier")
    return tuple(slots)


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
        if evidence_polarity(
            question,
            str(selector["text"]),
            desired_polarity="yes",
        )
        == polarity
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
    if (
        polarity is not None
        and evidence_polarity(
            question,
            " ".join(str(value["text"]) for value in ordered),
            desired_polarity="yes",
        )
        != polarity
    ):
        return None
    return ordered


def _spans_overlap(selectors: tuple[dict[str, Any], ...]) -> bool:
    previous_evidence_id = ""
    previous_end = -1
    for selector in selectors:
        evidence_id = str(selector["evidence_id"])
        if evidence_id != previous_evidence_id:
            previous_evidence_id = evidence_id
            previous_end = -1
        start = int(selector["span_start"])
        end = int(selector["span_end"])
        if start < previous_end:
            return True
        previous_end = end
    return False
