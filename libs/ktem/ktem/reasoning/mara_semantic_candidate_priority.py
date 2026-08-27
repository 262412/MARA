from __future__ import annotations

import re

from .mara_qasper_candidate_relation import (
    candidate_relation_anchor,
    candidate_slot_hints,
)


def candidate_record_slot_hints(question: str, text: str) -> tuple[str, ...]:
    """Return the strongest exact-clause slot hints without joining unrelated text."""

    sentence_fragments = (
        match.group(0).strip()
        for match in re.finditer(r".+?(?:[.!?](?=\s|$)|\n+|$)", text, re.DOTALL)
    )
    fragments = [
        clause.strip()
        for sentence in sentence_fragments
        for clause in re.split(
            r"(?:;|,\s*(?:but|while|whereas|although|however)\s+)",
            sentence,
            flags=re.IGNORECASE,
        )
        if clause.strip()
    ]
    clause_hints = [
        tuple(candidate_slot_hints(question, fragment))
        for fragment in fragments or [text]
    ]
    return max(
        clause_hints,
        key=lambda hints: (
            len(hints),
            int("quantifier" in hints),
            int("predicate" in hints),
            tuple(hints),
        ),
        default=(),
    )


def semantic_record_priority(
    question: str,
    text: str,
    *,
    candidate_priority: bool,
    polarity_priority: int,
    alignment_score: float,
    slot_priority: int,
    ranked_position: int,
) -> tuple[int | float, ...]:
    if not candidate_priority:
        return polarity_priority, slot_priority, ranked_position, -alignment_score
    slot_hints = candidate_record_slot_hints(question, text)
    return (
        0 if candidate_relation_anchor(question, text) else 1,
        0 if "quantifier" in slot_hints else 1,
        -len(slot_hints),
        polarity_priority,
        -alignment_score,
        slot_priority,
        ranked_position,
    )


def candidate_source_fields(text: str, *, enabled: bool) -> dict[str, object]:
    if not enabled:
        return {}
    return {"candidate_source_text": text, "candidate_source_text_start": 0}
