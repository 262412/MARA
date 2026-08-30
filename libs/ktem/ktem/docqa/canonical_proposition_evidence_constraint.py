from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .canonical_proposition_evidence_plan import canonical_evidence_set_analysis
from .question_proposition import (
    QuestionProposition,
    applicable_proposition_evidence_slots,
)
from .semantic_relation_clause_lexical import semantic_content_token_set


@dataclass(frozen=True, slots=True)
class CanonicalEvidenceConstraintProjection:
    bound_slots: tuple[str, ...]
    covered_object_tokens: tuple[str, ...]
    reason: str


def semantic_constraint_observation(
    analyses: Sequence[Mapping[str, Any]],
    proposition: QuestionProposition,
) -> tuple[list[str], list[str], list[str], list[str]]:
    required_slots = list(applicable_proposition_evidence_slots(proposition))
    bound_slots = sorted(
        {
            str(slot)
            for analysis in analyses
            for slot in analysis.get("slot_evidence") or {}
            if analysis.get("relation_bearing") is True
            and analysis.get("meta_scope") is not True
        }
    )
    required_object_tokens = sorted(
        semantic_content_token_set(proposition.object_surface)
    )
    covered_object_tokens = sorted(
        {
            str(token)
            for analysis in analyses
            if analysis.get("relation_bearing") is True
            and analysis.get("meta_scope") is not True
            and "object" in (analysis.get("slot_evidence") or {})
            for token in analysis.get("covered_object_tokens") or []
        }
    )
    return required_slots, bound_slots, required_object_tokens, covered_object_tokens


def canonical_evidence_constraint_projection(
    premises: Sequence[Mapping[str, Any]],
    proposition: QuestionProposition,
    verdict: str,
    *,
    required_slots: Sequence[str],
    required_object_tokens: Sequence[str],
) -> CanonicalEvidenceConstraintProjection | None:
    selectors = _canonical_plan_selectors(premises)
    if selectors is None or verdict not in {"yes", "no"}:
        return None
    required_objects = set(required_object_tokens)
    bound_slots = tuple(
        sorted(
            {
                str(slot)
                for selector in selectors
                for slot in selector.get("slot_hints") or []
            }
        )
    )
    covered_objects = tuple(
        sorted(
            {
                str(token)
                for selector in selectors
                for token in selector.get("object_tokens") or []
                if str(token) in required_objects
            }
        )
    )
    analysis = canonical_evidence_set_analysis(
        proposition.surface,
        selectors,
        required_slots,
        polarity_relation=(
            "proposition_support" if verdict == "yes" else "explicit_contradiction"
        ),
    )
    return CanonicalEvidenceConstraintProjection(
        bound_slots=bound_slots,
        covered_object_tokens=covered_objects,
        reason=_canonical_constraint_reason(str(analysis.get("reason") or "")),
    )


def _canonical_plan_selectors(
    premises: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...] | None:
    if not premises or any(not str(value.get("event_id") or "") for value in premises):
        return None
    return tuple(
        {
            "evidence_id": str(premise.get("evidence_id") or ""),
            "selector_id": str(premise.get("span_selector") or ""),
            "text": str(premise.get("quote") or ""),
            "span_start": premise.get("span_start"),
            "span_end": premise.get("span_end"),
            "slot_hints": list(premise.get("binds_proposition_slots") or []),
            "proposition_slot_spans": dict(premise.get("proposition_slot_spans") or {}),
            "object_tokens": list(premise.get("object_tokens") or []),
            "event_id": str(premise.get("event_id") or ""),
            "event_core_tokens": list(premise.get("event_core_tokens") or []),
            "predicate_match_kind": str(premise.get("predicate_match_kind") or ""),
            "local_relation_state": str(premise.get("local_relation_state") or ""),
        }
        for premise in premises
    )


def _canonical_constraint_reason(reason: str) -> str:
    mapped = {
        "": "",
        "evidence_set_missing": "local_semantic_relation_missing",
        "slot_coverage_incomplete": "local_semantic_slot_coverage_incomplete",
        "predicate_missing": "local_semantic_slot_coverage_incomplete",
        "object_coverage_incomplete": "local_semantic_object_coverage_incomplete",
        "quantifier_attachment_invalid": "local_semantic_quantifier_attachment_invalid",
        "event_binding_inconsistent": "local_semantic_event_binding_inconsistent",
        "predicate_argument_binding_incomplete": (
            "local_semantic_required_role_binding_incomplete"
        ),
        "support_conflicts_with_explicit_contradiction": (
            "local_semantic_relation_explicit_contradiction"
        ),
        "support_role_binding_incomplete": (
            "local_semantic_required_role_binding_incomplete"
        ),
        "support_relation_unresolved": "local_semantic_relation_unresolved",
        "explicit_contradiction_missing": (
            "local_semantic_explicit_contradiction_missing"
        ),
    }
    return mapped.get(reason, f"local_semantic_{reason}" if reason else "")
