from __future__ import annotations

import re

from .boolean_current_experiment import (
    is_current_experiment_question,
    is_direct_current_empirical_action,
)
from .boolean_evidence_scope import _scope_rejection


def proposition_scope_rejection(
    question: str,
    span: str,
    context: str,
    *,
    actor: str,
    section_role: str,
) -> str:
    rejection = _scope_rejection(
        question,
        actor=actor,
        section_role=section_role,
        structured_scope_available=True,
        quote=span,
    )
    if (
        not rejection
        and is_current_experiment_question(question)
        and not is_direct_current_empirical_action(span)
    ):
        return "current_experiment_action_not_established"
    deictic_actor = _deictic_method_actor(question)
    if (
        not rejection
        and deictic_actor
        and not _deictic_method_identity_is_bound(deictic_actor, span, context)
    ):
        return "deictic_method_identity_unbound"
    return rejection


def _deictic_method_actor(question: str) -> str:
    match = re.search(
        r"\bthis\s+(method|model|approach|system|framework|technique)\b",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    return match.group(1).lower() if match is not None else ""


def _deictic_method_identity_is_bound(
    actor_noun: str,
    span: str,
    context: str,
) -> bool:
    marker = re.compile(
        rf"\b(?:this|our|the\s+proposed|our\s+proposed|the\s+present|"
        rf"the\s+new)\s+{re.escape(actor_noun)}\b",
        flags=re.IGNORECASE,
    )
    return bool(marker.search(span) or marker.search(context))
