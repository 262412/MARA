from __future__ import annotations

import re
from typing import Any

from .boolean_evidence_scope import evidence_item_text
from .evidence_identity import identity_of
from .qasper_answer_relation import (
    _GENERIC_ANSWER_TERMS,
    AnswerRelationResolution,
    _answer_relation_candidate,
    _content_tokens,
    _numbers,
    _sentence_spans,
    _title_only,
    resolve_qasper_answer_relation,
)
from .qasper_relation_frame import QuestionRelationFrame, question_relation_frame

_LAYERED_RELATION_TERMS = {
    "account",
    "address",
    "also",
    "analy",
    "apply",
    "based",
    "built",
    "calculat",
    "contain",
    "describe",
    "detect",
    "evaluat",
    "find",
    "improv",
    "incorporat",
    "include",
    "introduc",
    "leverag",
    "method",
    "model",
    "novel",
    "perform",
    "provide",
    "rely",
    "represent",
    "use",
    "used",
    "uses",
    "using",
    "work",
}

_ANSWER_RELATION_SIGNALS = {
    "account_for": r"\baccount(?:s|ed|ing)?\s+for\b",
    "leverage": r"\b(?:leverag(?:e|es|ed|ing)|use(?:s|d|ing)?|"
    r"rel(?:y|ies|ied|ying)\s+on)\b",
    "rely_on": r"\b(?:rel(?:y|ies|ied|ying)\s+on|leverag(?:e|es|ed|ing)|"
    r"use(?:s|d|ing)?)\b",
    "use": r"\b(?:use(?:s|d|ing)?|leverag(?:e|es|ed|ing)|"
    r"rel(?:y|ies|ied|ying)\s+on)\b",
    "provide": r"\bprovid(?:e|es|ed|ing)\b",
    "contain": r"\bcontain(?:s|ed|ing)?\b",
    "include": r"\binclud(?:e|es|ed|ing)\b",
    "report": r"\breport(?:s|ed|ing)?\b",
    "describe": r"\bdescrib(?:e|es|ed|ing)\b",
    "identify": r"\bidentif(?:y|ies|ied|ying)\b",
    "recruit": r"\brecruit(?:s|ed|ing)?\b",
    "evaluate": r"\b(?:evaluat(?:e|es|ed|ing)|assess(?:es|ed|ing)?)\b",
    "train": r"\btrain(?:s|ed|ing)?\b",
    "improve": r"\b(?:improv(?:e|es|ed|ing|ement)|better|"
    r"outperform(?:s|ed|ing)?)\b",
    "novel": r"\b(?:novel(?:ty)?|new(?:ly)?|innovative|"
    r"based\s+on|built\s+on|address(?:es|ed|ing)?)\b",
    "baseline": r"\b(?:baseline|compar(?:e|es|ed|ing)\s+(?:with|to)|"
    r"reference\s+method)\b",
    "calculate": r"\bcalculat(?:e|es|ed|ing)\b",
    "compute": r"\bcomput(?:e|es|ed|ing)\b",
    "derive": r"\bderiv(?:e|es|ed|ing)\b",
    "apply": r"\bappl(?:y|ies|ied|ying)\b",
    "perform": r"\bperform(?:s|ed|ing)?\b",
    "create": r"\bcreat(?:e|es|ed|ing)\b",
    "collect": r"\bcollect(?:s|ed|ing)?\b",
    "cause": r"\b(?:caus(?:e|es|ed|ing)|drive|drove|driven|reason)\b",
    "demonstrate": r"\bdemonstrat(?:e|es|ed|ing)\b",
    "analyze": r"\banaly(?:ze|zes|zed|zing|se|ses|sed|sing)\b",
    "explore": r"\bexplor(?:e|es|ed|ing)\b",
    "address": r"\baddress(?:es|ed|ing)?\b",
    "achieve": r"\bachiev(?:e|es|ed|ing)\b",
    "find": r"\b(?:find|finds|found|finding)\b",
}


def resolve_qasper_answer_relation_layered(
    question: str,
    answer: str,
    evidence_items: list[dict[str, Any]],
    *,
    allowed_evidence_ids: set[str] | None = None,
) -> AnswerRelationResolution:
    """Resolve exact or controlled semantic answer-to-evidence relations.

    The public exact resolver remains fail-closed for direct contract checks.
    This layered resolver is used after claim verification has identified a
    candidate answer. A paraphrase is accepted only when its substantive
    object tokens occur in a sentence with the requested relation, scope, and
    actor; it does not turn topic overlap into authority.
    """

    exact = resolve_qasper_answer_relation(question, answer, evidence_items)
    exact_atoms = _allowed_atoms(exact.atoms, allowed_evidence_ids)
    if exact_atoms:
        return AnswerRelationResolution(
            "verified_support",
            exact.reason,
            tuple(exact_atoms),
        )
    if exact.reason == "quantity_answer_missing":
        return exact

    frame = question_relation_frame(question)
    if not frame.predicate:
        return AnswerRelationResolution("missing", "question_predicate_unresolved")
    question_tokens = _content_tokens(question)
    question_anchors = question_tokens - _GENERIC_ANSWER_TERMS
    answer_numbers = _numbers(answer)
    answer_clauses = [value[0] for value in _sentence_spans(answer)] or [answer]
    selected_atoms: list[dict[str, Any]] = []
    covered_question_anchors: set[str] = set()
    for clause in answer_clauses:
        atom, anchors, reason = _resolve_layered_answer_clause(
            question,
            clause,
            evidence_items,
            relation_kind=frame.relation_kind,
            frame=frame,
            question_tokens=question_tokens,
            question_anchors=question_anchors,
            answer_numbers=answer_numbers,
            previous_actor=(
                str(selected_atoms[-1].get("actor") or "") if selected_atoms else ""
            ),
            allowed_evidence_ids=allowed_evidence_ids,
        )
        if atom is None:
            return AnswerRelationResolution("missing", reason)
        selected_atoms.append(atom)
        covered_question_anchors.update(anchors)
    if len(covered_question_anchors) < min(2, len(question_anchors)):
        return AnswerRelationResolution("missing", "question_relation_unresolved")
    deduplicated = {
        (str(atom["evidence_id"]), str(atom["evidence_ref"])): atom
        for atom in selected_atoms
    }
    return AnswerRelationResolution(
        "verified_support",
        "layered_semantic_answer_relation",
        tuple(deduplicated[key] for key in sorted(deduplicated)),
    )


def answer_clause_has_relation_signal(question: str, clause: str) -> bool:
    """Return whether an answer clause states the question's relation."""

    predicate = question_relation_frame(question).predicate
    pattern = _ANSWER_RELATION_SIGNALS.get(predicate)
    return bool(pattern and re.search(pattern, str(clause or ""), re.IGNORECASE))


def layered_claim_revision_text(
    question: str,
    claim: str,
    atom: dict[str, Any],
) -> str:
    """Reduce a partially bound claim to the object backed by its atom."""

    question_tokens = _content_tokens(question)
    answer_values = _layered_answer_values(
        _content_tokens(claim),
        question_tokens,
        _numbers(claim),
    )
    object_text = str(atom.get("object") or "").strip()
    object_values = _content_tokens(object_text) | _numbers(object_text)
    if not object_text or not answer_values or answer_values <= object_values:
        return claim
    return object_text


def _resolve_layered_answer_clause(
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
    allowed_evidence_ids: set[str] | None,
) -> tuple[dict[str, Any] | None, set[str], str]:
    clause_tokens = _content_tokens(clause)
    clause_numbers = _numbers(clause)
    answer_values = _layered_answer_values(
        clause_tokens,
        question_tokens,
        clause_numbers,
    )
    if not answer_values:
        return None, set(), "answer_value_missing"
    candidates, title_only_seen = _layered_candidates(
        question,
        clause,
        evidence_items,
        relation_kind=relation_kind,
        frame=frame,
        question_anchors=question_anchors,
        answer_numbers=answer_numbers,
        clause_numbers=clause_numbers,
        answer_values=answer_values,
        previous_actor=previous_actor,
        allowed_evidence_ids=allowed_evidence_ids,
    )
    if not candidates:
        reason = (
            "title_only_evidence" if title_only_seen else "answer_relation_unresolved"
        )
        return None, set(), reason
    best_rank = min(value[0] for value in candidates)
    best_score = best_rank[:2]
    best = [value for value in candidates if value[0][:2] == best_score]
    if len({str(value[1].get("object") or "").casefold() for value in best}) > 1:
        return None, set(), "answer_relation_ambiguous"
    _rank, atom, anchors = min(best, key=lambda value: value[0])
    return atom, anchors, ""


def _layered_candidates(
    question: str,
    clause: str,
    evidence_items: list[dict[str, Any]],
    *,
    relation_kind: str,
    frame: QuestionRelationFrame,
    question_anchors: set[str],
    answer_numbers: set[str],
    clause_numbers: set[str],
    answer_values: set[str],
    previous_actor: str,
    allowed_evidence_ids: set[str] | None,
) -> tuple[list[tuple[Any, dict[str, Any], set[str]]], bool]:
    candidates: list[tuple[Any, dict[str, Any], set[str]]] = []
    title_only_seen = False
    content_sentence_seen = False
    for item in evidence_items:
        if allowed_evidence_ids is not None:
            try:
                if identity_of(item).key not in allowed_evidence_ids:
                    continue
            except ValueError:
                continue
        if _title_only(item):
            title_only_seen = True
            continue
        for quote, start, end in _sentence_spans(evidence_item_text(item)):
            if re.match(r"^\s*#{1,6}\s+\S", quote):
                title_only_seen = True
                continue
            content_sentence_seen = True
            supported_values = _layered_supported_values(
                frame,
                quote,
                answer_values,
                answer_numbers=answer_numbers,
            )
            if supported_values is None:
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
                novel_tokens=supported_values,
                answer_values=supported_values,
                previous_actor=previous_actor,
            )
            if candidate is not None:
                rank, atom, anchors = candidate
                rank = (
                    -len(supported_values) / max(1, len(answer_values)),
                    *rank[1:],
                )
                candidates.append(
                    (
                        rank,
                        {**atom, "reason": "layered_semantic_answer_relation"},
                        anchors,
                    )
                )
    return candidates, title_only_seen and not content_sentence_seen


def _layered_supported_values(
    frame: QuestionRelationFrame,
    quote: str,
    answer_values: set[str],
    *,
    answer_numbers: set[str],
) -> set[str] | None:
    quote_values = _content_tokens(quote) | _numbers(quote)
    supported = answer_values & quote_values
    if answer_numbers and not answer_numbers <= _numbers(quote):
        return None
    if frame.predicate == "account_for":
        return answer_values if answer_values <= quote_values else None
    minimum = 1 if len(answer_values) <= 1 else 2
    return supported if len(supported) >= minimum else None


def _layered_answer_values(
    clause_tokens: set[str],
    question_tokens: set[str],
    clause_numbers: set[str],
) -> set[str]:
    values = clause_tokens - question_tokens - _GENERIC_ANSWER_TERMS
    values -= _LAYERED_RELATION_TERMS
    return values or clause_numbers


def _allowed_atoms(
    atoms: tuple[dict[str, Any], ...],
    allowed_evidence_ids: set[str] | None,
) -> list[dict[str, Any]]:
    if allowed_evidence_ids is None:
        return list(atoms)
    return [
        atom
        for atom in atoms
        if str(atom.get("evidence_id") or "").strip() in allowed_evidence_ids
    ]
