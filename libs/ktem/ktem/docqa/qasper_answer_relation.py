from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .boolean_evidence_scope import evidence_item_text
from .evidence_identity import identity_of
from .qasper_relation_frame import QuestionRelationFrame, question_relation_frame
from .qasper_relation_frame import (
    question_scope_is_explicit as _question_scope_is_explicit,
)
from .qasper_relation_frame import relation_is_explicit as _relation_is_explicit
from .query_phrase_extraction import source_page_locator

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_NUMBER_RE = re.compile(
    r"(?<![a-z0-9])(?:\d+(?:\.\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten)(?![a-z0-9])",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}
_GENERIC_ANSWER_TERMS = {
    "answer",
    "author",
    "evidence",
    "paper",
    "report",
    "show",
    "study",
    "support",
}
_CURRENT_PAPER_TERMS = re.compile(
    r"\b(?:we|our|ours|this\s+(?:paper|study|work|approach)|the\s+authors?)\b",
    re.IGNORECASE,
)
_RELATED_WORK_TERMS = re.compile(
    r"\b(?:related\s+work|prior\s+work|previous\s+work|background|literature)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AnswerRelationResolution:
    state: str
    reason: str
    atoms: tuple[dict[str, Any], ...] = ()

    @property
    def atom(self) -> dict[str, Any] | None:
        return self.atoms[0] if self.atoms else None


def resolve_qasper_answer_relation(
    question: str,
    answer: str,
    evidence_items: list[dict[str, Any]],
) -> AnswerRelationResolution:
    frame = question_relation_frame(question)
    if not frame.predicate:
        return AnswerRelationResolution("missing", "question_predicate_unresolved")
    relation_kind = frame.relation_kind
    question_tokens = _content_tokens(question)
    answer_numbers = _numbers(answer)
    if relation_kind == "quantity" and not answer_numbers:
        return AnswerRelationResolution("missing", "quantity_answer_missing")
    question_anchors = question_tokens - _GENERIC_ANSWER_TERMS
    answer_clauses = [value[0] for value in _sentence_spans(answer)] or [answer]
    selected_atoms: list[dict[str, Any]] = []
    covered_question_anchors: set[str] = set()
    for clause in answer_clauses:
        atom, anchors, reason = _resolve_answer_clause(
            question,
            clause,
            evidence_items,
            relation_kind=relation_kind,
            frame=frame,
            question_tokens=question_tokens,
            question_anchors=question_anchors,
            answer_numbers=answer_numbers,
            previous_actor=(
                str(selected_atoms[-1].get("actor") or "") if selected_atoms else ""
            ),
        )
        if atom is None:
            return AnswerRelationResolution("missing", reason)
        selected_atoms.append(atom)
        covered_question_anchors.update(anchors)

    required_anchors = min(2, len(question_anchors))
    if len(covered_question_anchors) < required_anchors:
        return AnswerRelationResolution("missing", "question_relation_unresolved")
    deduplicated = {
        (str(atom["evidence_id"]), str(atom["evidence_ref"])): atom
        for atom in selected_atoms
    }
    return AnswerRelationResolution(
        "verified_support",
        "exact_question_answer_relation",
        tuple(deduplicated[key] for key in sorted(deduplicated)),
    )


def _resolve_answer_clause(
    question: str,
    clause: str,
    evidence_items: list[dict[str, Any]],
    *,
    relation_kind: str,
    frame: QuestionRelationFrame,
    question_tokens: set[str],
    question_anchors: set[str],
    answer_numbers: set[str],
    previous_actor: str,
) -> tuple[dict[str, Any] | None, set[str], str]:
    clause_tokens = _content_tokens(clause)
    clause_numbers = _numbers(clause)
    novel_tokens = clause_tokens - question_tokens - _GENERIC_ANSWER_TERMS
    answer_values = novel_tokens or clause_numbers
    if not answer_values:
        return None, set(), "answer_value_missing"
    candidates = []
    title_only_seen = False
    for item in evidence_items:
        if _title_only(item):
            title_only_seen = True
            continue
        for quote, start, end in _sentence_spans(evidence_item_text(item)):
            if re.match(r"^\s*#{1,6}\s+\S", quote):
                title_only_seen = True
                continue
            candidate = _answer_relation_candidate(
                item,
                quote,
                start,
                end,
                question=question,
                clause=clause,
                relation_kind=relation_kind,
                frame=frame,
                question_anchors=question_anchors,
                answer_numbers=answer_numbers,
                clause_numbers=clause_numbers,
                novel_tokens=novel_tokens,
                answer_values=answer_values,
                previous_actor=previous_actor,
            )
            if candidate is not None:
                candidates.append(candidate)
    if not candidates:
        reason = (
            "title_only_evidence" if title_only_seen else "answer_relation_unresolved"
        )
        return None, set(), reason
    _rank, atom, anchors = min(candidates, key=lambda value: value[0])
    return atom, anchors, ""


def _answer_relation_candidate(
    item: dict[str, Any],
    quote: str,
    start: int,
    end: int,
    *,
    question: str,
    clause: str,
    relation_kind: str,
    frame: QuestionRelationFrame,
    question_anchors: set[str],
    answer_numbers: set[str],
    clause_numbers: set[str],
    novel_tokens: set[str],
    answer_values: set[str],
    previous_actor: str,
) -> tuple[tuple[float, float, int, str, int], dict[str, Any], set[str]] | None:
    quote_tokens = _content_tokens(quote)
    quote_numbers = _numbers(quote)
    supported_values = answer_values & (quote_tokens | quote_numbers)
    coverage = len(supported_values) / max(1, len(answer_values))
    if coverage < 1.0 or not _relation_is_explicit(
        frame,
        quote,
        answer_numbers=answer_numbers,
        quote_numbers=quote_numbers,
    ):
        return None
    if not _answer_values_bind_to_relation(frame, quote, answer_values):
        return None
    if not _question_scope_is_explicit(frame, quote):
        return None
    anchors = quote_tokens & question_anchors
    actor = _resolved_actor(item, quote, question, clause, anchors, previous_actor)
    if actor == "unknown" or (
        _requires_current_paper_actor(question) and actor != "current_paper"
    ):
        return None
    atom = _answer_relation_atom(
        item,
        quote,
        start,
        end,
        question=question,
        answer_clause=clause,
        relation_kind=relation_kind,
        frame=frame,
        answer_values=answer_values,
        answer_numbers=answer_numbers,
        actor=actor,
    )
    if atom is None:
        return None
    rank = (
        -coverage,
        -(len(anchors) / max(1, len(question_anchors))),
        len(quote),
        str(atom["evidence_id"]),
        start,
    )
    return rank, atom, anchors


def _answer_values_bind_to_relation(
    frame: QuestionRelationFrame,
    quote: str,
    answer_values: set[str],
) -> bool:
    if frame.predicate != "account_for":
        return True
    relation = re.search(r"\baccount(?:s|ed|ing)?\s+for\b", quote, re.I)
    if relation is None:
        return False
    suffix = quote[relation.end() :]
    passive_actor = re.match(
        r"\s+by\s+(?:this\s+work|this\s+paper|us|the\s+authors?)\b",
        suffix,
        re.I,
    )
    if passive_actor is not None:
        prefix = quote[: relation.start()]
        auxiliary = re.search(
            r"\b(?:is|are|was|were|be|been|being)(?:\s+\w+){0,3}\s*$",
            prefix,
            re.I,
        )
        argument_span = prefix[: auxiliary.start()] if auxiliary else prefix
    else:
        argument_span = suffix
    argument_span = re.split(
        r";|\b(?:while|whereas|but|although|however)\b",
        argument_span,
        maxsplit=1,
        flags=re.I,
    )[0]
    return answer_values <= _content_tokens(argument_span)


def _resolved_actor(
    item: dict[str, Any],
    quote: str,
    question: str,
    clause: str,
    anchors: set[str],
    previous_actor: str,
) -> str:
    actor = _actor(item, quote)
    if (
        actor == "unknown"
        and previous_actor == "current_paper"
        and re.match(r"^\s*(?:it|this|they|these)\b", quote, re.I)
    ):
        return "current_paper"
    if actor == "unknown" and _local_answer_relation_establishes_actor(
        question,
        quote,
        clause,
        anchors,
    ):
        return "current_paper"
    return actor


def _answer_relation_atom(
    item: dict[str, Any],
    quote: str,
    start: int,
    end: int,
    *,
    question: str,
    answer_clause: str,
    relation_kind: str,
    frame: QuestionRelationFrame,
    answer_values: set[str],
    answer_numbers: set[str],
    actor: str,
) -> dict[str, Any] | None:
    required_qualifiers = {
        value
        for value in (_qualifier(question), _qualifier(answer_clause))
        if value != "none"
    }
    quote_qualifier = _qualifier(quote)
    if required_qualifiers and required_qualifiers != {quote_qualifier}:
        return None
    try:
        evidence_id = identity_of(item).key
    except ValueError:
        return None
    canonical_base = next(
        (
            value
            for value in (
                _optional_int(item.get("canonical_start")),
                _optional_int(item.get("chunk_start")),
            )
            if value is not None
        ),
        None,
    )
    canonical_start = canonical_base + start if canonical_base is not None else None
    canonical_end = canonical_base + end if canonical_base is not None else None
    span_start = canonical_start if canonical_start is not None else start
    span_end = canonical_end if canonical_end is not None else end
    evidence_ref = f"{evidence_id}#quote:{span_start}:{span_end}"
    source_id, page_label = source_page_locator(item)
    relation = frame.predicate
    quantifier = sorted(answer_numbers)[0] if answer_numbers else "none"
    object_value = _answer_object_value(answer_clause, answer_values)
    if not object_value:
        return None
    section_scope = _section_scope(item)
    return {
        "evidence_id": evidence_id,
        "evidence_ref": evidence_ref,
        "span_id": evidence_ref,
        "quote": quote,
        "span_start": start,
        "span_end": end,
        "canonical_start": canonical_start,
        "canonical_end": canonical_end,
        "source_id": source_id,
        "page_label": page_label,
        "actor": actor,
        "relation": relation,
        "predicate": relation,
        "object": object_value,
        "arguments": [object_value],
        "object_role": frame.expected_object_role,
        "object_type": frame.expected_object_type,
        "qualifier": quote_qualifier,
        "quantifier": quantifier,
        "scope": section_scope,
        "section_scope": section_scope,
        "question_scope": frame.scope,
        "polarity": "",
        "reason": "exact_question_answer_relation",
    }


def _answer_object_value(
    answer_clause: str,
    answer_values: set[str],
) -> str:
    values = []
    seen: set[str] = set()
    for token in _TOKEN_RE.findall(str(answer_clause or "")):
        normalized = _stem(token.lower())
        if normalized in answer_values and normalized not in seen:
            seen.add(normalized)
            values.append(token)
    return " ".join(values)


def _local_answer_relation_establishes_actor(
    question: str,
    quote: str,
    clause: str,
    clause_anchors: set[str],
) -> bool:
    if not clause_anchors or _RELATED_WORK_TERMS.search(quote):
        return False
    if re.search(r"\bbibref\d+\b|\bet\s+al\.?\b", quote, re.IGNORECASE):
        return False
    subject_terms = {
        "approach",
        "author",
        "method",
        "model",
        "paper",
        "study",
        "system",
        "work",
    }
    question_subjects = _content_tokens(question) & subject_terms
    quote_tokens = _content_tokens(quote)
    exact_clause = " ".join(clause.lower().split()).rstrip(".?!") == " ".join(
        quote.lower().split()
    ).rstrip(".?!")
    return bool(question_subjects & quote_tokens and exact_clause)


def answer_relation_candidate_score(
    question: str,
    item: dict[str, Any],
) -> float:
    if _title_only(item):
        return 0.0
    question_tokens = _content_tokens(question) - _GENERIC_ANSWER_TERMS
    item_tokens = _content_tokens(evidence_item_text(item))
    if not question_tokens or not item_tokens:
        return 0.0
    overlap = len(question_tokens & item_tokens)
    return overlap / len(question_tokens) if overlap else 0.0


def _actor(item: dict[str, Any], quote: str) -> str:
    section = _section_scope(item)
    if _RELATED_WORK_TERMS.search(section) or _RELATED_WORK_TERMS.search(quote):
        return "cited_work"
    if _CURRENT_PAPER_TERMS.search(quote) or section in {
        "abstract",
        "conclusion",
        "discussion",
        "experiment",
        "experiments",
        "method",
        "methods",
        "result",
        "results",
    }:
        return "current_paper"
    return "unknown"


def _requires_current_paper_actor(question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:authors?|paper|study|work|approach|model|method|proposed|we|our|they|their)\b",
            question,
            re.IGNORECASE,
        )
    )


def _section_scope(item: dict[str, Any]) -> str:
    value = " ".join(
        str(item.get(key) or "").strip()
        for key in ("section_id", "section_title", "section", "heading")
        if str(item.get(key) or "").strip()
    ).lower()
    return value or "document"


def _title_only(item: dict[str, Any]) -> bool:
    kind = " ".join(
        str(item.get(key) or "").lower()
        for key in ("element_type", "modality", "section_id", "section_title")
    )
    return bool(re.search(r"\btitle\b|\bheading\b", kind))


def _sentence_spans(text: str) -> list[tuple[str, int, int]]:
    output: list[tuple[str, int, int]] = []
    for match in _SENTENCE_RE.finditer(text):
        raw = match.group(0)
        leading = len(raw) - len(raw.lstrip())
        quote = raw.strip()
        if not quote:
            continue
        start = match.start() + leading
        output.append((quote, start, start + len(quote)))
    return output


def _content_tokens(value: str) -> set[str]:
    return {
        _stem(token)
        for token in _TOKEN_RE.findall(str(value or "").lower())
        if token not in _STOPWORDS
    }


def _stem(token: str) -> str:
    if re.fullmatch(r"repr?esent(?:ed|ing|s)?", token):
        return "represent"
    aliases = {
        "authors": "author",
        "participants": "participant",
        "recruited": "recruit",
        "recruiting": "recruit",
        "relied": "rely",
        "relies": "rely",
        "relying": "rely",
        "leveraged": "leverage",
        "leverages": "leverage",
        "leveraging": "leverage",
        "represents": "represent",
        "represented": "represent",
        "studies": "study",
    }
    if token in aliases:
        return aliases[token]
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) > len(suffix) + 3:
            return token[: -len(suffix)]
    return token


def _numbers(value: str) -> set[str]:
    return {match.group(0).lower() for match in _NUMBER_RE.finditer(str(value or ""))}


def _qualifier(*values: str) -> str:
    text = " ".join(values).lower()
    match = re.search(
        r"\b(?:at\s+least|at\s+most|more\s+than|less\s+than|only|approximately|now)\b",
        text,
    )
    return match.group(0) if match else "none"


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
