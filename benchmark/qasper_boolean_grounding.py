from __future__ import annotations

from typing import Any

from .qasper_boolean import (
    boolean_complete_quote_conflicts,
    boolean_quote_is_grounded,
    boolean_quote_supports_relation,
    boolean_relation_lemmas,
    corrected_complete_requirement_polarity,
    quality_control_relation_polarity,
)
from .qasper_boolean_scope import (
    BooleanScopeDecision,
    evidence_item_text,
    validate_boolean_scope,
)
from .qasper_proposition_conflict import resolve_boolean_conflict


def ground_boolean_verdict(
    *,
    question: str,
    evidence: str,
    verdict: str,
    quote: str,
    evidence_items: list[dict[str, Any]] | None,
) -> tuple[str, str, bool, bool, str, dict[str, str]]:
    raw_verdict = verdict
    quality_control_polarity = (
        quality_control_relation_polarity(question, quote) if quote else ""
    )
    relation_trace = {
        "question_relation_terms": ",".join(sorted(boolean_relation_lemmas(question))),
        "quote_relation_terms": ",".join(sorted(boolean_relation_lemmas(quote))),
    }
    quote_grounded = boolean_quote_is_grounded(quote, evidence) or any(
        boolean_quote_is_grounded(quote, evidence_item_text(item))
        for item in (evidence_items or [])
    )
    typed_polarity = {"yes_complete": "yes", "no_complete": "no"}.get(
        raw_verdict,
        "",
    )
    scope = _initial_boolean_scope(
        question,
        quote,
        typed_polarity,
        quote_grounded,
        evidence_items,
    )
    if scope is not None:
        relation_trace.update(scope.as_trace())
    verdict, supported, reason, conflict = grounded_boolean_relation(
        raw_verdict,
        question=question,
        quote=quote,
        quote_grounded=quote_grounded,
        scope=scope,
    )
    if conflict is not None:
        relation_trace["deterministic_relation_conflict"] = str(conflict).lower()
    verdict, supported, reason = _enforce_boolean_scope(
        question=question,
        quote=quote,
        verdict=verdict,
        supported=supported,
        reason=reason,
        scope=scope,
        quality_control_polarity=quality_control_polarity,
        evidence_items=evidence_items,
        relation_trace=relation_trace,
    )
    return verdict, raw_verdict, quote_grounded, supported, reason, relation_trace


def resolve_grounded_boolean_conflict(
    question: str,
    evidence: str,
    candidate_polarity: str,
    *,
    verdict: str,
    evidence_items: list[dict[str, Any]] | None,
    relation_trace: dict[str, str],
    authoritative_support: Any,
) -> tuple[str, str, dict[str, str]]:
    scope_valid = relation_trace.get("boolean_scope_valid") != "false"
    return resolve_boolean_conflict(
        evidence if scope_valid else "",
        question,
        candidate_polarity=candidate_polarity,
        verdict=verdict,
        evidence_items=evidence_items if scope_valid else [],
        authoritative_claim_key=(
            authoritative_support.claim_key if authoritative_support else None
        ),
        authoritative_evidence_id=(
            authoritative_support.evidence_id if authoritative_support else ""
        ),
        authoritative_polarity=(
            authoritative_support.polarity if authoritative_support else ""
        ),
        authoritative_quote=(
            authoritative_support.quote if authoritative_support else ""
        ),
    )


def _initial_boolean_scope(
    question: str,
    quote: str,
    typed_polarity: str,
    quote_grounded: bool,
    evidence_items: list[dict[str, Any]] | None,
) -> BooleanScopeDecision | None:
    if not typed_polarity or not quote_grounded:
        return None
    return validate_boolean_scope(
        question,
        quote,
        typed_polarity,
        evidence_items=evidence_items,
    )


def _enforce_boolean_scope(
    *,
    question: str,
    quote: str,
    verdict: str,
    supported: bool,
    reason: str,
    scope: BooleanScopeDecision | None,
    quality_control_polarity: str,
    evidence_items: list[dict[str, Any]] | None,
    relation_trace: dict[str, str],
) -> tuple[str, bool, str]:
    if verdict not in {"yes", "no"} or quality_control_polarity:
        return verdict, supported, reason
    if scope is None:
        scope = validate_boolean_scope(
            question,
            quote,
            verdict,
            evidence_items=evidence_items,
        )
        relation_trace.update(scope.as_trace())
    if scope.scope_valid:
        return verdict, supported, reason
    return "insufficient_evidence", False, scope.reason


def grounded_boolean_relation(
    raw_verdict: str,
    *,
    question: str,
    quote: str,
    quote_grounded: bool,
    scope: BooleanScopeDecision | None,
) -> tuple[str, bool, str, bool | None]:
    complete = {"yes_complete": "yes", "no_complete": "no"}
    if raw_verdict in complete:
        return _ground_complete_boolean_relation(
            complete[raw_verdict],
            question=question,
            quote=quote,
            quote_grounded=quote_grounded,
            scope=scope,
        )
    quality_control_polarity = (
        quality_control_relation_polarity(question, quote) if quote_grounded else ""
    )
    if quality_control_polarity:
        return quality_control_polarity, True, "grounded_complete_proposition", False
    if raw_verdict in {"yes_partial", "no_partial"}:
        reason = (
            "grounded_partial_proposition" if quote_grounded else "ungrounded_quote"
        )
        return "insufficient_evidence", False, reason, None
    if raw_verdict == "insufficient_evidence":
        return raw_verdict, False, "insufficient_evidence", None
    supported = quote_grounded and boolean_quote_supports_relation(
        quote,
        question,
        raw_verdict,
    )
    if not quote_grounded:
        reason = "ungrounded_quote"
    elif not supported:
        reason = "grounded_quote_incomplete_relation"
    else:
        reason = "grounded_complete_relation"
    return (
        raw_verdict if supported else "insufficient_evidence",
        supported,
        reason,
        None,
    )


def _ground_complete_boolean_relation(
    polarity: str,
    *,
    question: str,
    quote: str,
    quote_grounded: bool,
    scope: BooleanScopeDecision | None,
) -> tuple[str, bool, str, bool | None]:
    quality_control_polarity = (
        quality_control_relation_polarity(question, quote) if quote_grounded else ""
    )
    if quality_control_polarity:
        return (
            quality_control_polarity,
            True,
            "grounded_complete_proposition",
            quality_control_polarity != polarity,
        )
    relation_supported = boolean_quote_supports_relation(
        quote,
        question,
        polarity,
    ) or bool(scope is not None and scope.scope_valid and scope.quantifier == "only")
    conflict = (
        quote_grounded
        and not (scope is not None and scope.scope_valid and scope.quantifier == "only")
        and boolean_complete_quote_conflicts(quote, question, polarity)
    )
    corrected = corrected_complete_requirement_polarity(
        quote,
        question,
        polarity,
    )
    if quote_grounded and corrected:
        return corrected, True, "grounded_complete_proposition", True
    supported = quote_grounded and (relation_supported or conflict)
    if not quote_grounded:
        reason = "ungrounded_quote"
    elif not supported:
        reason = "grounded_quote_incomplete_relation"
    else:
        reason = "grounded_complete_proposition"
    return (
        polarity if supported else "insufficient_evidence",
        supported,
        reason,
        bool(corrected),
    )
