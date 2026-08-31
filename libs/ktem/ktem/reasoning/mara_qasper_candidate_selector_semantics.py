from __future__ import annotations

import re
from typing import Any

from ktem.docqa.qasper_semantic_pack_contract import canonical_payload_digest
from ktem.docqa.question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
)
from ktem.docqa.semantic_relation_clause_lexical import (
    canonical_proposition_object_token_set,
    semantic_content_token_set,
)
from ktem.docqa.semantic_relation_clause_validation import (
    semantic_relation_clause_analysis,
    semantic_slot_evidence_projection,
)

from .mara_qasper_selector_semantic_alignment import (
    attested_selector_alignment_slot_span,
    attested_selector_slot_span,
    auditable_target_relation_present,
    build_local_selector_semantic_alignment,
    predicate_surface_is_auditable,
)
from .mara_qasper_selector_semantic_alignment_contract import (
    verified_selector_semantic_alignment,
)

__all__ = [
    "auditable_target_relation_present",
    "build_local_selector_semantic_alignment",
    "verified_selector_semantic_alignment",
]

_PROPOSITION_SLOTS = ("actor", "predicate", "object", "quantifier")
_TITLE_MARKER_RE = re.compile(r"(?:^\s*#|\s:::\s|@!START@|@!END@)", re.IGNORECASE)


def candidate_polarity_signal(question: str, text: str) -> str:
    proposition = build_question_proposition(question)
    required_object_tokens = canonical_proposition_object_token_set(proposition)
    if not required_object_tokens <= semantic_content_token_set(text):
        return "undetermined"
    semantics = revalidated_selector_semantics({}, question, text)
    return str(semantics["polarity_signal"])


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
    return list(revalidated_selector_semantics(selector, question, text)["slots"])


def selector_direct_polarity_evidence(
    selector: dict[str, Any],
    question: str,
    text: str,
) -> bool:
    semantics = revalidated_selector_semantics(selector, question, text)
    return bool(
        semantics["relation_bearing"]
        and semantics["local_relation_state"]
        in {"affirmative_assertion", "explicit_contradiction"}
    )


def selector_polarity_signal(
    selector: dict[str, Any],
    question: str,
    text: str,
) -> str:
    return str(
        revalidated_selector_semantics(selector, question, text)["polarity_signal"]
    )


def revalidated_selector_semantics(
    selector: dict[str, Any],
    question: str,
    text: str,
) -> dict[str, Any]:
    """Recompute proposition binding without trusting persisted declarations."""

    direct = _direct_selector_semantics(selector, question, text)
    alignment = verified_selector_semantic_alignment(question, selector)
    if alignment is not None:
        _apply_verified_alignment(direct, selector, alignment)
    elif str(selector.get("predicate_match_kind") or "").strip() == "paraphrase":
        direct.update(
            slots=[],
            slot_spans={},
            relation_bearing=False,
            local_relation_state="unbound",
        )
    local_state = str(direct["local_relation_state"])
    polarity_signal = {
        "affirmative_assertion": "support",
        "explicit_contradiction": "explicit_contradiction",
    }.get(local_state, "undetermined")
    uncertainty_context = bool(direct.pop("uncertainty_context"))
    direct.pop("applicable_slots")
    return {
        **direct,
        "slot_spans": {slot: direct["slot_spans"][slot] for slot in direct["slots"]},
        "candidate_relation_role": (
            "uncertainty_context" if uncertainty_context else "polarity_evidence"
        ),
        "polarity_signal": polarity_signal,
        "semantic_alignment": alignment,
    }


def _direct_selector_semantics(
    selector: dict[str, Any],
    question: str,
    text: str,
) -> dict[str, Any]:
    proposition = build_question_proposition(question)
    applicable = applicable_proposition_evidence_slots(proposition)
    analysis = semantic_relation_clause_analysis(
        {"quote": text, "binds_proposition_slots": list(applicable)}, proposition
    )
    title_like = bool(_TITLE_MARKER_RE.search(text))
    observed_spans = dict(analysis.get("slot_evidence") or {})
    target_relation_present = analysis.get("target_relation_present") is True
    if not predicate_surface_is_auditable(proposition, text):
        target_relation_present = False
        observed_spans.pop("predicate", None)
    if title_like:
        observed_spans = {}
    slots = [slot for slot in applicable if slot in observed_spans]
    relation_bearing = bool(not title_like and analysis.get("relation_bearing") is True)
    direct_negation = analysis.get("direct_relation_negated")
    direct_anchor = bool(
        relation_bearing
        and target_relation_present
        and analysis.get("meta_scope") is not True
        and isinstance(direct_negation, bool)
    )
    raw_state = str(analysis.get("status") or "unbound")
    uncertainty_context = bool(
        not slots and relation_bearing and target_relation_present
    )
    local_state = _direct_local_state(
        raw_state,
        uncertainty_context=uncertainty_context,
        direct_anchor=direct_anchor,
        direct_negation=bool(direct_negation),
    )
    return {
        "slots": slots,
        "slot_spans": _direct_slot_spans(selector, text, analysis),
        "relation_bearing": relation_bearing,
        "uncertainty_context": uncertainty_context,
        "local_relation_state": local_state,
        "local_relation_analysis_digest": str(analysis.get("analysis_digest") or ""),
        "analysis": analysis,
        "applicable_slots": applicable,
    }


def _direct_local_state(
    raw_state: str,
    *,
    uncertainty_context: bool,
    direct_anchor: bool,
    direct_negation: bool,
) -> str:
    if uncertainty_context:
        return raw_state
    if direct_anchor:
        return "explicit_contradiction" if direct_negation else "affirmative_assertion"
    return raw_state


def _direct_slot_spans(
    selector: dict[str, Any],
    text: str,
    analysis: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    raw_span_base = selector.get("span_start")
    span_base = (
        raw_span_base
        if isinstance(raw_span_base, int) and not isinstance(raw_span_base, bool)
        else 0
    )
    selector_id = str(selector.get("selector_id") or "")
    slot_spans = semantic_slot_evidence_projection(
        analysis,
        premise_ref=selector_id,
        span_base=span_base,
    )
    for child in slot_spans.values():
        child.update(
            parent_selector_id=selector_id,
            parent_span_start=span_base,
            parent_span_end=span_base + len(text),
            parent_text_digest=canonical_payload_digest(text),
            text_digest=canonical_payload_digest(str(child.get("text") or "")),
        )
    return slot_spans


def _apply_verified_alignment(
    direct: dict[str, Any],
    selector: dict[str, Any],
    alignment: dict[str, Any],
) -> None:
    aligned = set(dict(alignment.get("slot_refs") or {}))
    slots = [slot for slot in direct["applicable_slots"] if slot in aligned]
    direct["slots"] = slots
    direct["uncertainty_context"] = False
    direct["local_relation_state"] = str(alignment.get("local_relation_state") or "")
    if "predicate" in slots:
        direct["relation_bearing"] = True
    for slot in slots:
        if slot == "object":
            direct["slot_spans"][slot] = attested_selector_alignment_slot_span(
                selector,
                alignment,
                slot,
                base_span=direct["slot_spans"].get(slot),
            )
        else:
            direct["slot_spans"].setdefault(
                slot,
                attested_selector_slot_span(selector, slot),
            )
