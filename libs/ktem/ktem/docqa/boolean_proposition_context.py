from __future__ import annotations

import re
from dataclasses import dataclass

from .boolean_empirical_actions import empirical_action_present
from .boolean_evidence_scope import (
    _actor,
    _prior_work_scope_question,
    _requires_current_paper_scope,
)
from .boolean_proposition_tokens import (
    _content_tokens,
    _object_token,
    _relation_surface_tokens,
)
from .boolean_relations import boolean_relation_lemmas, primary_boolean_relation
from .boolean_scope_language import named_language_pair_present

_MAX_CONTEXT_SENTENCES = 5
_MAX_CONTEXT_DISTANCE = 3
_MAX_CONTEXT_CHARS = 1400
_MAX_QUALIFIED_EMPIRICAL_SENTENCES = 6
_MAX_QUALIFIED_EMPIRICAL_DISTANCE = 5
_EXPLICIT_CLASSIFICATION_RE = re.compile(
    r"\b(?:is|are|was|were|can\s+be)\s+"
    r"(?:(?:explicitly|commonly|generally)\s+)?"
    r"(?:treated|classified|considered|regarded)(?:\s+as)?\b",
    flags=re.IGNORECASE,
)
_QUALIFIED_CATEGORY_TOKENS = {"corpus", "dataset", "language", "task"}
_GENERIC_EMPIRICAL_BRIDGE_TOKENS = {
    "approach",
    "baseline",
    "component",
    "data",
    "dataset",
    "experiment",
    "language",
    "method",
    "model",
    "performance",
    "result",
    "system",
    "task",
    "toolkit",
}


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


def bounded_proposition_context(text: str, span: str, *, question: str = "") -> str:
    window = exact_proposition_context(text, span, question=question)
    return window.text if window is not None else span


def exact_proposition_context(
    text: str,
    span: str,
    *,
    canonical_start: int | None = None,
    question: str = "",
) -> PropositionContextWindow | None:
    """Return the smallest bounded continuous window completing a proposition."""

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
        first, last = _semantic_window_indices(
            source,
            statements,
            index,
            question=question,
        )
        start = statements[first][0]
        end = statements[last][1]
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


def _semantic_window_indices(
    text: str,
    statements: list[tuple[int, int]],
    target_index: int,
    *,
    question: str,
) -> tuple[int, int]:
    if not str(question or "").strip():
        return target_index, target_index
    first = target_index
    last = target_index
    best_score = _semantic_frame_score(
        question,
        _statement_window_text(text, statements, first, last),
    )
    for distance in range(1, _MAX_QUALIFIED_EMPIRICAL_DISTANCE + 1):
        candidates = []
        if target_index - distance >= 0:
            candidates.append((target_index - distance, last))
        if target_index + distance < len(statements):
            candidates.append((first, target_index + distance))
        for candidate_first, candidate_last in candidates:
            candidate_first = min(first, candidate_first)
            candidate_last = max(last, candidate_last)
            sentence_count = candidate_last - candidate_first + 1
            if sentence_count > _MAX_QUALIFIED_EMPIRICAL_SENTENCES:
                continue
            candidate_text = _statement_window_text(
                text,
                statements,
                candidate_first,
                candidate_last,
            )
            extended = bool(
                distance > _MAX_CONTEXT_DISTANCE
                or sentence_count > _MAX_CONTEXT_SENTENCES
            )
            if (
                len(candidate_text) > _MAX_CONTEXT_CHARS
                or _crosses_section_boundary(candidate_text)
                or _crosses_actor_boundary(
                    text,
                    statements,
                    candidate_first,
                    candidate_last,
                )
                or (
                    extended
                    and not qualified_empirical_context(question, candidate_text)
                )
            ):
                continue
            score = _semantic_frame_score(question, candidate_text)
            if score > best_score:
                first, last, best_score = candidate_first, candidate_last, score
    return first, last


def qualified_empirical_context(question: str, value: str) -> bool:
    """Allow a longer window only for an explicit empirical category bridge."""

    if primary_boolean_relation(question) != "evaluate":
        return False
    relation_tokens = _relation_surface_tokens("evaluate")
    clauses = re.split(
        r"(?:\r?\n)+|(?<=[.!?;])\s+|\s+(?:but|however|whereas)\s+",
        str(value or ""),
        flags=re.IGNORECASE,
    )
    empirical_clauses = [
        clause for clause in clauses if empirical_action_present(clause)
    ]
    for empirical_clause in empirical_clauses:
        empirical_tokens = normalized_object_tokens(empirical_clause, relation_tokens)
        for context_clause in clauses:
            if context_clause == empirical_clause:
                continue
            context_tokens = normalized_object_tokens(context_clause, relation_tokens)
            if qualified_category_bridge(
                question,
                empirical_tokens,
                context_tokens,
                context_clause,
                relation_tokens,
            ):
                return True
    return False


def specific_empirical_bridge_tokens(
    empirical_tokens: set[str],
    context_tokens: set[str],
) -> set[str]:
    return (empirical_tokens & context_tokens) - _GENERIC_EMPIRICAL_BRIDGE_TOKENS


def qualified_category_bridge(
    question: str,
    empirical_tokens: set[str],
    context_tokens: set[str],
    context_clause: str,
    relation_tokens: set[str],
) -> bool:
    question_tokens = normalized_object_tokens(question, relation_tokens)
    category = (
        question_tokens & empirical_tokens & context_tokens & _QUALIFIED_CATEGORY_TOKENS
    )
    qualifiers = (
        (question_tokens & context_tokens)
        - empirical_tokens
        - _GENERIC_EMPIRICAL_BRIDGE_TOKENS
    )
    return bool(
        category and qualifiers and _EXPLICIT_CLASSIFICATION_RE.search(context_clause)
    )


def _semantic_frame_score(
    question: str, context: str
) -> tuple[int, float, int, int, int]:
    question_relations = boolean_relation_lemmas(question)
    context_relations = boolean_relation_lemmas(context)
    relation_score = int(
        not question_relations or bool(question_relations & context_relations)
    )
    relation_tokens = {
        token
        for relation in question_relations
        for token in _relation_surface_tokens(relation)
    }
    question_objects = normalized_object_tokens(question, relation_tokens) - {""}
    context_objects = normalized_object_tokens(context, relation_tokens) - {""}
    if (
        "task" in question_objects
        and re.search(r"\b(?:these|those|aforementioned)\s+tasks?\b", question, re.I)
        and context_relations
        and context_objects
    ):
        object_score = 1.0
    elif question_objects:
        object_score = len(question_objects & context_objects) / len(question_objects)
    else:
        object_score = 1.0
    actor = _actor(context, "unknown")
    if _prior_work_scope_question(question):
        actor_score = int(actor in {"cited_work", "other_authors"})
    elif _requires_current_paper_scope(question):
        actor_score = int(actor == "current_paper")
    else:
        actor_score = int(actor != "unknown")
    qualifier_score = _qualifier_specificity(context)
    complete_count = actor_score + relation_score + int(object_score >= 1.0)
    return complete_count, object_score, actor_score, relation_score, qualifier_score


def _qualifier_specificity(value: str) -> int:
    lowered = str(value or "").lower()
    if re.search(
        r"\b(?:little|minimal|negligible|almost\s+no|no)\s+"
        r"(?:useful\s+)?(?:information|evidence|benefit|gain|impact)\b",
        lowered,
    ):
        return 3
    if re.search(
        r"\b(?:non[- ]?significant|insignificant|not\s+significant)\b", lowered
    ):
        return 2
    if re.search(r"\b(?:small|minor|marginal)\w*\b", lowered):
        return 1
    return 0


def _statement_window_text(
    text: str,
    statements: list[tuple[int, int]],
    first: int,
    last: int,
) -> str:
    return text[statements[first][0] : statements[last][1]].strip()


def _crosses_section_boundary(value: str) -> bool:
    return bool(re.search(r"(?:^|\n)\s*#{1,6}\s+", value))


def _crosses_actor_boundary(
    text: str,
    statements: list[tuple[int, int]],
    first: int,
    last: int,
) -> bool:
    actors = {
        actor
        for index in range(first, last + 1)
        if (
            actor := _actor(
                _statement_window_text(text, statements, index, index),
                "unknown",
            )
        )
        in {"current_paper", "cited_work", "other_authors"}
    }
    return "current_paper" in actors and bool(actors & {"cited_work", "other_authors"})


def _sentence_offsets(text: str) -> list[tuple[int, int]]:
    protected = re.sub(r"(?<=\d)\.(?=\d)", "\x00", str(text or ""))
    return [
        (candidate.start(), candidate.end())
        for candidate in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", protected)
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
    if re.search(
        r"\b(?:task\s+bank|bank\s+of(?:\s+over)?\s+\w+\s+tasks?|"
        r"(?:collection|catalog|suite)\s+of\s+(?:\w+\s+){0,2}tasks?)\b",
        str(value or ""),
        flags=re.IGNORECASE,
    ):
        normalized.add("dataset")
        normalized.discard("bank")
    if {"semantic", "role", "induction"} <= raw_tokens:
        normalized.discard("induction")
    parallel_resources = raw_tokens & {
        "corpora",
        "corpus",
        "data",
        "dataset",
        "datasets",
    }
    if "parallel" in raw_tokens and parallel_resources:
        normalized.discard("parallel")
        normalized -= {_object_token(token) for token in parallel_resources}
        normalized.add("parallel_data")
    if named_language_pair_present(value):
        normalized.update({"language", "pair"})
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
