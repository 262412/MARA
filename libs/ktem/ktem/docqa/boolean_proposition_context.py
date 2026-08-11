from __future__ import annotations

import re
from dataclasses import dataclass

from .boolean_evidence_scope import (
    _actor,
    _prior_work_scope_question,
    _requires_current_paper_scope,
)
from .boolean_proposition_tokens import _content_tokens, _object_token
from .boolean_relations import boolean_relation_lemmas, primary_boolean_relation


@dataclass(frozen=True)
class PropositionContextWindow:
    text: str
    start: int
    end: int
    canonical_start: int | None = None
    canonical_end: int | None = None

    def as_dict(self) -> dict[str, int | str | None]:
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "canonical_start": self.canonical_start,
            "canonical_end": self.canonical_end,
        }


def contextual_actor(span: str, context: str, section_role: str) -> str:
    actor = _actor(span, section_role)
    if actor != "unknown" or section_role in {"related_work", "future_work"}:
        return actor
    contextual = _actor(context, section_role)
    return "current_paper" if contextual == "current_paper" else actor


def semantic_resolution_text(question: str, span: str, context: str) -> str:
    question_relations = boolean_relation_lemmas(question)
    span_relations = boolean_relation_lemmas(span)
    if (
        question_relations
        and span_relations
        and not (question_relations & span_relations)
    ):
        return span
    return context


def bounded_proposition_context(text: str, span: str) -> str:
    window = exact_proposition_context(text, span)
    return window.text if window is not None else span


def exact_proposition_context(
    text: str,
    span: str,
    *,
    canonical_start: int | None = None,
) -> PropositionContextWindow | None:
    """Return one exact, continuous one-to-three sentence authority window."""

    source = str(text or "")
    target = str(span or "")
    matches = list(re.finditer(re.escape(target), source)) if target else []
    if len(matches) != 1:
        return None
    match = matches[0]
    statements = _sentence_offsets(source)
    index = next(
        (
            index
            for index, (start, end) in enumerate(statements)
            if start <= match.start() and match.end() <= end
        ),
        None,
    )
    if index is None:
        start, end = match.span()
    else:
        start = statements[max(0, index - 1)][0]
        end = statements[min(len(statements) - 1, index + 1)][1]
    while start < end and source[start].isspace():
        start += 1
    while end > start and source[end - 1].isspace():
        end -= 1
    absolute_start = canonical_start + start if canonical_start is not None else None
    absolute_end = canonical_start + end if canonical_start is not None else None
    return PropositionContextWindow(
        text=source[start:end],
        start=start,
        end=end,
        canonical_start=absolute_start,
        canonical_end=absolute_end,
    )


def _sentence_offsets(text: str) -> list[tuple[int, int]]:
    return [
        (candidate.start(), candidate.end())
        for candidate in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", str(text or ""))
        if candidate.group(0).strip()
    ]


def actor_scope_scores(
    actor: str,
    question: str,
    section_role: str,
    scope_rejection: str,
) -> tuple[float, float]:
    actor_score = float(
        actor == "current_paper"
        or (
            actor in {"cited_work", "other_authors"}
            and _prior_work_scope_question(question)
        )
        or (actor == "unknown" and not _requires_current_paper_scope(question))
    )
    scope_score = float(
        section_role != "future_work"
        and (section_role != "related_work" or _prior_work_scope_question(question))
        and not scope_rejection
    )
    return actor_score, scope_score


def normalized_object_tokens(value: str, relation_tokens: set[str]) -> set[str]:
    raw_tokens = _content_tokens(value) - relation_tokens
    normalized = {_object_token(token) for token in raw_tokens}
    parallel_resources = raw_tokens & {
        "corpora",
        "corpus",
        "data",
        "dataset",
        "datasets",
    }
    if "parallel" in raw_tokens and parallel_resources:
        normalized -= {_object_token(token) for token in parallel_resources}
        normalized.add("parallel_data")
    return normalized


def proposition_spans(question: str, text: str) -> list[str]:
    protected = re.sub(
        r"\bet\s+al\.",
        "et al<dot>",
        str(text or ""),
        flags=re.IGNORECASE,
    )
    statements = re.split(r"(?:\r?\n)+|(?<=[.!?])\s+|\s*;\s*", protected)
    target = primary_boolean_relation(question)
    output: list[str] = []
    for statement in statements:
        clauses = re.split(
            r"\s+(?:but|however|yet|whereas)\s+",
            statement,
            flags=re.IGNORECASE,
        )
        for clause in clauses:
            clause = clause.replace("<dot>", ".").strip()
            if clause:
                output.extend(_split_target_conjunction(clause, target))
    return output


def _split_target_conjunction(value: str, target: str) -> list[str]:
    if not target or " and " not in value.lower():
        return [value]
    parts = re.split(r"\s+and\s+", value, flags=re.IGNORECASE)
    target_parts = [part for part in parts if target in boolean_relation_lemmas(part)]
    relational_parts = [part for part in parts if boolean_relation_lemmas(part)]
    return target_parts if len(relational_parts) > 1 and target_parts else [value]
