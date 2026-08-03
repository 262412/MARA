from __future__ import annotations

from .qasper_boolean import (
    boolean_complete_quote_conflicts,
    boolean_quote_supports_relation,
    corrected_complete_requirement_polarity,
    quality_control_relation_polarity,
)
from .qasper_boolean_scope import BooleanScopeDecision


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
        polarity = complete[raw_verdict]
        quality_control_polarity = (
            quality_control_relation_polarity(question, quote)
            if quote_grounded
            else ""
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
        )
        conflict = (
            quote_grounded
            and not (
                scope is not None and scope.scope_valid and scope.quantifier == "only"
            )
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
