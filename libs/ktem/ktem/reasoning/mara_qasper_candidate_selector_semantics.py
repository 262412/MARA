from __future__ import annotations

from typing import Any

from ktem.docqa.question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
)
from ktem.docqa.semantic_relation_clause_lexical import semantic_content_token_set
from ktem.docqa.semantic_relation_clause_validation import (
    semantic_relation_clause_analysis,
)

from .mara_qasper_candidate_relation import candidate_slot_hints

_PROPOSITION_SLOTS = ("actor", "predicate", "object", "quantifier")


def candidate_polarity_signal(question: str, text: str) -> str:
    proposition = build_question_proposition(question)
    required_object_tokens = semantic_content_token_set(proposition.object_surface)
    if not required_object_tokens <= semantic_content_token_set(text):
        return "undetermined"
    analysis = semantic_relation_clause_analysis(
        {
            "quote": text,
            "binds_proposition_slots": list(
                applicable_proposition_evidence_slots(proposition)
            ),
        },
        proposition,
    )
    observed = str(analysis.get("status") or "")
    return {
        "affirmative_assertion": "support",
        "explicit_contradiction": "explicit_contradiction",
    }.get(observed, "undetermined")


def evidence_polarity_priority(question: str, text: str) -> int:
    """Prefer explicit support or contradiction over unresolved text."""

    observed = candidate_polarity_signal(question, text)
    return 0 if observed in {"support", "explicit_contradiction"} else 1


def required_candidate_slots(question: str) -> tuple[str, ...]:
    return applicable_candidate_slots(question)


def applicable_candidate_slots(question: str) -> tuple[str, ...]:
    proposition = build_question_proposition(question)
    slots = list(_PROPOSITION_SLOTS[:-1])
    quantifier = " ".join(str(proposition.quantifier or "").casefold().split())
    if quantifier in {"", "none"}:
        return tuple(slots)
    slots.append("quantifier")
    return tuple(slots)


def candidate_structural_features(
    question: str,
    selected: tuple[dict[str, Any], ...] | None,
    *,
    applicable_slots: tuple[str, ...],
) -> list[str]:
    if not selected:
        return []
    proposition = build_question_proposition(question)
    features: list[str] = []
    if len(selected) > 1:
        features.append("cross_span")
    if "quantifier" in applicable_slots and any(
        "quantifier" in selector.get("slot_hints", []) for selector in selected
    ):
        features.append("quantifier")
    predicate_surface = str(proposition.predicate or "").replace("_", " ").casefold()
    if any(
        "predicate" in selector.get("slot_hints", [])
        and predicate_surface not in str(selector.get("text") or "").casefold()
        for selector in selected
    ):
        features.append("paraphrase")
    subject_surface = " ".join(
        str(proposition.subject_surface or "").casefold().split()
    )
    if subject_surface and any(
        "actor" in selector.get("slot_hints", [])
        and subject_surface
        not in " ".join(str(selector.get("text") or "").casefold().split())
        for selector in selected
    ):
        features.append("entity_alias")
    return features


def spans_overlap(selectors: tuple[dict[str, Any], ...]) -> bool:
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


def selector_local_slots(
    selector: dict[str, Any],
    question: str,
    text: str,
) -> list[str]:
    if "allowed_proposition_slots" in selector:
        return [
            str(slot)
            for slot in selector.get("allowed_proposition_slots") or []
            if str(slot) in _PROPOSITION_SLOTS
        ]
    return candidate_slot_hints(question, text)


def selector_direct_polarity_evidence(selector: dict[str, Any]) -> bool:
    state = str(selector.get("local_relation_state") or "")
    if state:
        return bool(
            selector.get("relation_bearing") is True
            and state in {"affirmative_assertion", "explicit_contradiction"}
        )
    return True


def selector_polarity_signal(
    selector: dict[str, Any],
    question: str,
    text: str,
) -> str:
    state = str(selector.get("local_relation_state") or "")
    if state:
        return {
            "affirmative_assertion": "support",
            "explicit_contradiction": "explicit_contradiction",
        }.get(state, "undetermined")
    return _local_relation_anchor_signal(question, text)


def _local_relation_anchor_signal(question: str, text: str) -> str:
    proposition = build_question_proposition(question)
    analysis = semantic_relation_clause_analysis(
        {
            "quote": text,
            "binds_proposition_slots": ["predicate"],
        },
        proposition,
    )
    negated = analysis.get("direct_relation_negated")
    if (
        analysis.get("relation_bearing") is not True
        or analysis.get("target_relation_present") is not True
        or analysis.get("meta_scope") is True
        or not isinstance(negated, bool)
    ):
        return "undetermined"
    return "explicit_contradiction" if negated else "support"
