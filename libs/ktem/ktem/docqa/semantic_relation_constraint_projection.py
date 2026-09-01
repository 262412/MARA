from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .canonical_proposition_evidence_constraint import (
    canonical_evidence_constraint_projection,
)
from .qasper_boolean_no_evidence import (
    qasper_no_evidence_set_analysis,
    qasper_support_evidence_binding_complete,
)
from .question_proposition import QuestionProposition


def legacy_constraint_projection(
    premises: Sequence[Mapping[str, Any]],
    proposition: QuestionProposition,
    verdict: str,
    *,
    analyses: list[dict[str, Any]],
    required_slots: list[str],
    bound_slots: list[str],
    required_object_tokens: list[str],
    covered_object_tokens: list[str],
) -> tuple[list[str], list[str], str, dict[str, Any], bool]:
    no_evidence_semantics, support_binding_complete = qasper_evidence_semantics(
        proposition,
        premises,
    )
    canonical = (
        canonical_evidence_constraint_projection(
            premises,
            proposition,
            verdict,
            required_slots=required_slots,
            required_object_tokens=required_object_tokens,
        )
        if all(analysis.get("assertion_scope") == "asserted" for analysis in analyses)
        else None
    )
    if canonical is not None:
        return (
            list(canonical.bound_slots),
            list(canonical.covered_object_tokens),
            canonical.reason,
            no_evidence_semantics,
            support_binding_complete,
        )
    reason = evidence_set_reason(
        analyses,
        verdict,
        required_slots=required_slots,
        bound_slots=bound_slots,
        required_object_tokens=required_object_tokens,
        covered_object_tokens=covered_object_tokens,
        no_evidence_semantics=no_evidence_semantics,
        support_evidence_binding_complete=support_binding_complete,
    )
    return (
        bound_slots,
        covered_object_tokens,
        reason,
        no_evidence_semantics,
        support_binding_complete,
    )


def qasper_evidence_semantics(
    proposition: QuestionProposition,
    premises: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    return (
        qasper_no_evidence_set_analysis(proposition.surface, premises),
        qasper_support_evidence_binding_complete(proposition.surface, premises),
    )


def evidence_set_reason(
    analyses: list[dict[str, Any]],
    verdict: str,
    *,
    required_slots: list[str],
    bound_slots: list[str],
    required_object_tokens: list[str],
    covered_object_tokens: list[str],
    no_evidence_semantics: Mapping[str, Any],
    support_evidence_binding_complete: bool,
) -> str:
    if not analyses:
        return "local_semantic_relation_missing"
    if any(value.get("status") == "mention_only" for value in analyses):
        return "local_semantic_relation_mention_only"
    if any(value.get("assertion_scope") != "asserted" for value in analyses):
        return "local_semantic_relation_unasserted_scope"
    if (
        verdict == "no"
        and no_evidence_semantics.get("admissible_as_explicit_contradiction")
        is not True
    ):
        return "local_semantic_explicit_contradiction_missing"
    if set(bound_slots) != set(required_slots):
        return "local_semantic_slot_coverage_incomplete"
    if set(covered_object_tokens) != set(required_object_tokens):
        return "local_semantic_object_coverage_incomplete"
    if verdict == "yes":
        if not support_evidence_binding_complete:
            return "local_semantic_required_role_binding_incomplete"
        if any(
            value.get("direct_relation_negated") is True
            and value.get("target_relation_present") is True
            and value.get("meta_scope") is not True
            for value in analyses
        ):
            return "local_semantic_relation_explicit_contradiction"
        if not any(
            value.get("direct_relation_negated") is False
            and value.get("target_relation_present") is True
            and value.get("meta_scope") is not True
            for value in analyses
        ):
            return "local_semantic_relation_unresolved"
        return ""
    if verdict == "no":
        if no_evidence_semantics.get("classification") == "explicit_negation" and any(
            value.get("direct_relation_negated") is False
            and value.get("target_relation_present") is True
            and value.get("meta_scope") is not True
            and "predicate" in (value.get("declared_proposition_slots") or [])
            for value in analyses
        ):
            return "local_semantic_relation_conflict"
        return ""
    return "local_semantic_relation_verdict_invalid"
