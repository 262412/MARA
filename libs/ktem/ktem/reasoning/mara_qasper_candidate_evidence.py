from __future__ import annotations

import re
from typing import Any

from ktem.docqa.boolean_evidence_scope import _actor
from ktem.docqa.boolean_proposition_polarity import evidence_polarity
from ktem.docqa.boolean_proposition_tokens import _content_tokens, _object_token
from ktem.docqa.question_proposition import build_question_proposition

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
    options: list[dict[str, Any]] = []
    for selector in record.get("selectors") or []:
        if not isinstance(selector, dict) or not _exact_selector_valid(selector):
            continue
        selector_text = str(selector.get("text") or "")
        slot_hints = candidate_slot_hints(question, selector_text)
        jointly_aligned = set(slot_hints) == set(_PROPOSITION_SLOTS)
        options.append(
            {
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


def candidate_polarity_signal(question: str, text: str) -> str:
    if set(candidate_slot_hints(question, text)) != set(_PROPOSITION_SLOTS):
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
        return True
    tokens = set(re.findall(r"[a-z0-9]+", str(text or "").casefold()))
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
        if isinstance(selector, dict) and _exact_selector_valid(selector)
    )


def _exact_selector_valid(selector: dict[str, Any]) -> bool:
    selector_id = str(selector.get("selector_id") or "").strip()
    text = str(selector.get("text") or "")
    start = selector.get("span_start")
    end = selector.get("span_end")
    return bool(
        selector_id
        and text
        and isinstance(start, int)
        and not isinstance(start, bool)
        and isinstance(end, int)
        and not isinstance(end, bool)
        and start >= 0
        and end > start
        and end - start == len(text)
    )


def exact_candidate_slot_binding(
    slot: dict[str, Any],
    records: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Return only a verified, all-slot, exact span binding from upstream state."""

    declared_refs = {
        str(value).strip()
        for value in slot.get("evidence_refs", [])
        if str(value).strip()
    }
    declared_bindings = slot.get("proposition_slot_bindings")
    if not declared_refs or not isinstance(declared_bindings, dict):
        return [], []
    if set(declared_bindings) != {"actor", "predicate", "object", "quantifier"}:
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
    if any(
        not str(declared_bindings[name] or "").strip()
        or " ".join(str(declared_bindings[name]).casefold().split())
        != " ".join(str(expected_bindings[name] or "").casefold().split())
        for name in expected_bindings
    ):
        return [], []
    evidence_bindings = slot.get("proposition_slot_evidence_refs")
    if not isinstance(evidence_bindings, dict) or set(evidence_bindings) != set(
        declared_bindings
    ):
        return [], []
    per_slot_refs = {
        slot_name: candidate_declared_refs(evidence_bindings.get(slot_name))
        for slot_name in declared_bindings
    }
    if any(not refs or not refs <= declared_refs for refs in per_slot_refs.values()):
        return [], []
    if set().union(*per_slot_refs.values()) != declared_refs:
        return [], []
    available_refs = {
        selector_id
        for record in records
        for selector_id in candidate_selector_ids(record)
    }
    if not declared_refs <= available_refs:
        return [], []
    ids = list(
        dict.fromkeys(
            str(record.get("evidence_id") or "")
            for record in records
            if declared_refs & set(candidate_selector_ids(record))
        )
    )
    return ids, sorted(declared_refs)


def candidate_declared_refs(value: Any) -> set[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        return set()
    return {str(ref).strip() for ref in values if str(ref).strip()}
