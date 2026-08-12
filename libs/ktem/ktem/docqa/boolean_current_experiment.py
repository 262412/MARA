from __future__ import annotations

import re
from typing import Any

from .evidence_identity import identity_of


def is_current_experiment_question(question: str) -> bool:
    lowered = str(question or "").lower()
    return bool(
        re.search(
            r"\b(?:(?:the\s+)?authors?|they|(?:this|current) "
            r"(?:paper|study|work))\b",
            lowered,
        )
        and re.search(
            r"\b(?:(?:conduct|perform|run|carry out)\w*\s+"
            r"(?:an?\s+)?experiments?|experiment(?:ed|s|ing)?)\b",
            lowered,
        )
        and re.search(
            r"\b(?:tasks?|benchmarks?|data|dataset|datasets|corpus)\b", lowered
        )
    )


def is_direct_current_empirical_action(value: str) -> bool:
    lowered = str(value or "")
    if not re.search(
        r"\b(?:i|we|our|(?:the\s+)?authors?|(?:this|current) "
        r"(?:paper|study|work))\b",
        lowered,
        flags=re.IGNORECASE,
    ):
        return False
    if re.search(
        r"\b(?:could|may|might|will|would|plans?\s+to|intend(?:s|ed)?\s+to)\b",
        lowered,
        flags=re.IGNORECASE,
    ):
        return False
    if re.search(
        r"\b(?:future|hypothetical|prospective|potential)\s+"
        r"(?:work|study|experiments?|evaluation|tests?)\b",
        lowered,
        flags=re.IGNORECASE,
    ):
        return False
    if re.search(
        r"\b(?:(?:do|does|did|have|has|had|was|were|is|are)\s+"
        r"(?:not|never)\s+|never\s+)"
        r"(?:conduct|perform|run|carry\s+out|experiment|evaluat|test|"
        r"measur|observe|observed|observes|observing|observation)\w*\b|"
        r"\b(?:no|without)\s+"
        r"(?:experiments?|evaluation|testing|tests?)\b",
        lowered,
        flags=re.IGNORECASE,
    ):
        return False
    empirical_action = re.search(
        r"\b(?:experiment|evaluat|test|unable to construct|ran|measur|"
        r"observation|observe)\w*\b",
        lowered,
        flags=re.IGNORECASE,
    )
    direct_translation = re.search(
        r"\b(?:i|we|(?:the\s+)?authors?)\s+"
        r"(?:have\s+|had\s+|also\s+|directly\s+)*translat\w*\b",
        lowered,
        flags=re.IGNORECASE,
    )
    return bool(empirical_action or direct_translation)


def current_experiment_excerpt(text: str) -> str:
    statements = [
        statement.strip()
        for statement in re.split(r"(?:\r?\n)+|(?<=[.!?])\s+", str(text or ""))
        if statement.strip()
    ]
    candidates = [
        statement
        for statement in statements
        if is_direct_current_empirical_action(statement)
    ]
    return max(candidates, key=_current_experiment_statement_score, default="")


def resolve_current_experiment_question(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> Any | None:
    if not is_current_experiment_question(question):
        return None

    from .boolean_evidence_scope import (
        ClosedScopeResolution,
        classify_boolean_evidence,
        evidence_item_text,
        validate_boolean_scope,
    )

    candidates: list[tuple[dict[str, Any], str, Any, str]] = []
    for item in evidence_items:
        text = evidence_item_text(item)
        quote = current_experiment_excerpt(text) if text else ""
        if not quote:
            continue
        scope_item = {
            **item,
            "text": quote,
            "ocr_text": "",
            "vlm_text": "",
            "caption": "",
        }
        assessment = classify_boolean_evidence(question, "yes", scope_item)
        # A current-experiment sentence is only a closed-scope resolution when
        # its *exact* proposition matches the requested relation and object.
        # Falling back to ``yes`` for any experiment-shaped sentence lets a
        # mention such as "we use BioBERT" answer a question about unrelated
        # tasks.  Retrieval may still keep that sentence as a candidate, but
        # authority must remain unknown until a typed proposition is bound.
        polarity = (
            str(assessment.proposition.polarity or "")
            if assessment.classification in {"supports", "contradicts"}
            and assessment.relation_score > 0
            and assessment.object_score >= 0.6
            else ""
        )
        if (
            not polarity
            and re.search(
                r"\b(?:these|those|aforementioned)\s+tasks?\b|"
                r"\btasks?\s+mentioned\b",
                str(question or ""),
                flags=re.IGNORECASE,
            )
            and is_direct_current_empirical_action(quote)
        ):
            # The existing QASPER deictic task contract treats a direct
            # empirical action as evidence for the previously introduced task
            # set.  Keep that narrow compatibility path, but never apply it
            # to open-ended objects such as "other tasks".
            polarity = "yes"
        if polarity not in {"yes", "no"}:
            continue
        decision = validate_boolean_scope(
            question,
            quote,
            polarity,
            evidence_items=[scope_item],
        )
        if decision.scope_valid:
            candidates.append((item, quote, decision, polarity))
    polarities = {value[3] for value in candidates}
    if len(polarities) != 1:
        return None
    polarity = polarities.pop()
    item, quote, decision, _polarity = min(
        (value for value in candidates if value[3] == polarity),
        key=lambda value: len(value[1]),
    )
    return ClosedScopeResolution(
        polarity=polarity,
        evidence_quote=quote,
        decision=decision,
        evidence_item=item,
    )


def _current_experiment_statement_score(statement: str) -> int:
    lowered = statement.lower()
    score = 0
    if re.search(r"\b(?:i|we|our|the authors?)\b", lowered):
        score += 2
    if re.search(
        r"\b(?:unable to construct|evaluat|experiment|measur|"
        r"observe|observed|observes|observing|observation|ran|tested)\w*\b",
        lowered,
    ):
        score += 2
    if re.search(r"\b(?:could|may|might|will|would)\b", lowered):
        score -= 3
    return score


def current_experiment_slot_score(
    question: str,
    item: dict[str, Any],
) -> float | None:
    if not is_current_experiment_question(question):
        return None
    from .boolean_evidence_scope import evidence_item_text, resolve_closed_scope_boolean

    resolution = resolve_closed_scope_boolean(question, [item])
    if resolution is None or resolution.polarity not in {"yes", "no"}:
        return 0.0
    if identity_of(resolution.evidence_item).key != identity_of(item).key:
        return 0.0
    quote = str(resolution.evidence_quote or "")
    if not quote or quote not in evidence_item_text(item):
        return 0.0
    scope = resolution.decision
    if not (
        scope.scope_valid
        and scope.actor == "current_paper"
        and is_direct_current_empirical_action(quote)
    ):
        return 0.0
    return 1.0
