from __future__ import annotations

import re
from typing import Any

from ktem.docqa.boolean_evidence_scope import classify_boolean_evidence_set

from .qasper_boolean import boolean_quote_supports_relation, stemmed_content_tokens

MIN_BOOLEAN_SUPPORT_SCORE = 0.35
MIN_BOOLEAN_SUPPORT_MARGIN = 0.10


def resolve_boolean_conflict(
    evidence: str,
    question: str,
    *,
    candidate_polarity: str,
    verdict: str,
    evidence_items: list[dict[str, Any]] | None = None,
    authoritative_claim_key: tuple[str, ...] | None = None,
    authoritative_polarity: str = "",
) -> tuple[str, str, dict[str, str]]:
    candidate_scores = _support_scores(
        evidence,
        question,
        candidate_polarity,
        evidence_items=evidence_items,
    )
    candidate_score = max(candidate_scores.values(), default=0.0)
    conflict_polarity = authoritative_polarity or candidate_polarity
    opposite = (
        "no" if conflict_polarity == "yes" else "yes" if conflict_polarity else ""
    )
    opposite_scores = _support_scores(
        evidence,
        question,
        opposite,
        evidence_items=evidence_items,
    )
    common_keys = set(candidate_scores) & set(opposite_scores)
    if authoritative_claim_key is not None:
        contradiction_score = opposite_scores.get(authoritative_claim_key, 0.0)
        same_proposition_conflict = authoritative_claim_key in opposite_scores
    else:
        contradiction_score = max(
            (opposite_scores[key] for key in common_keys),
            default=(
                max(opposite_scores.values(), default=0.0)
                if not candidate_scores
                else 0.0
            ),
        )
        same_proposition_conflict = bool(common_keys)
    verdict_scores = _support_scores(
        evidence,
        question,
        verdict,
        evidence_items=evidence_items,
    )
    verdict_score = (
        1.0
        if authoritative_claim_key is not None and verdict == authoritative_polarity
        else max(verdict_scores.values(), default=0.0)
    )
    action, answer, conflict_status = _boolean_answer_action(
        candidate_polarity,
        verdict,
        candidate_support_score=candidate_score,
        contradiction_score=contradiction_score,
        verdict_support_score=verdict_score,
        same_proposition_conflict=same_proposition_conflict,
    )
    return (
        action,
        answer,
        {
            "candidate_support_score": f"{candidate_score:.3f}",
            "contradiction_score": f"{contradiction_score:.3f}",
            "verdict_support_score": f"{verdict_score:.3f}",
            "selected_polarity": answer if answer in {"yes", "no"} else "abstain",
            "conflict_status": conflict_status,
            "abstention_reason": conflict_status if answer == "unanswerable" else "",
        },
    )


def _support_scores(
    evidence: str,
    question: str,
    polarity: str,
    *,
    evidence_items: list[dict[str, Any]] | None,
) -> dict[tuple[str, ...], float]:
    if evidence_items is not None:
        classified = classify_boolean_evidence_set(
            question,
            polarity,
            evidence_items,
        )
        scores: dict[tuple[str, ...], float] = {}
        for assessment in classified.supports:
            key = assessment.proposition.claim_key
            scores[key] = max(
                scores.get(key, 0.0),
                assessment.relation_score * assessment.object_score,
            )
        return scores
    score = _proposition_support_score(evidence, question, polarity)
    return {("legacy_text",): score} if score > 0 else {}


def _boolean_answer_action(
    candidate_polarity: str,
    verdict: str,
    *,
    candidate_support_score: float,
    contradiction_score: float,
    verdict_support_score: float,
    same_proposition_conflict: bool,
) -> tuple[str, str, str]:
    if verdict not in {"yes", "no"}:
        if (
            candidate_polarity
            and candidate_support_score >= MIN_BOOLEAN_SUPPORT_SCORE
            and candidate_support_score - contradiction_score
            >= MIN_BOOLEAN_SUPPORT_MARGIN
        ):
            return (
                "preserved_candidate_conflict_warning",
                candidate_polarity,
                "candidate_support_dominates",
            )
        action = (
            "abstained_insufficient_evidence"
            if candidate_polarity
            else "preserved_boolean_abstention"
        )
        return action, "unanswerable", "insufficient_evidence"
    if (
        same_proposition_conflict
        and verdict_support_score >= MIN_BOOLEAN_SUPPORT_SCORE
        and contradiction_score >= MIN_BOOLEAN_SUPPORT_SCORE
    ):
        return "abstained_polarity_conflict", "unanswerable", "balanced_conflict"
    if not candidate_polarity:
        if verdict_support_score >= MIN_BOOLEAN_SUPPORT_SCORE:
            return "recovered_boolean_from_abstention", verdict, "none"
        return "preserved_boolean_abstention", "unanswerable", "insufficient_evidence"
    if verdict == candidate_polarity:
        if candidate_support_score >= MIN_BOOLEAN_SUPPORT_SCORE:
            return "confirmed_candidate", verdict, "none"
        return (
            "abstained_insufficient_evidence",
            "unanswerable",
            "insufficient_evidence",
        )
    if (
        candidate_support_score >= MIN_BOOLEAN_SUPPORT_SCORE
        and candidate_support_score - contradiction_score >= MIN_BOOLEAN_SUPPORT_MARGIN
    ):
        return (
            "preserved_candidate_conflict_warning",
            candidate_polarity,
            "candidate_support_dominates",
        )
    if (
        same_proposition_conflict
        and candidate_support_score >= MIN_BOOLEAN_SUPPORT_SCORE
        and contradiction_score >= MIN_BOOLEAN_SUPPORT_SCORE
    ):
        return "abstained_polarity_conflict", "unanswerable", "balanced_conflict"
    if verdict_support_score >= MIN_BOOLEAN_SUPPORT_SCORE:
        return "corrected_polarity", verdict, "opposite_support_only"
    return "abstained_insufficient_evidence", "unanswerable", "insufficient_evidence"


def _proposition_support_score(
    evidence: str,
    question: str,
    polarity: str,
) -> float:
    if polarity not in {"yes", "no"}:
        return 0.0
    question_tokens = stemmed_content_tokens(question)
    if not question_tokens:
        return 0.0
    best = 0.0
    passages = re.split(r"(?:\r?\n)+|(?<=[.!?])\s+", str(evidence or ""))
    for passage in passages:
        if not boolean_quote_supports_relation(passage, question, polarity):
            continue
        if not _legacy_relation_polarity_matches(question, passage, polarity):
            continue
        passage_tokens = stemmed_content_tokens(passage)
        coverage = len(question_tokens & passage_tokens) / len(question_tokens)
        best = max(best, coverage, MIN_BOOLEAN_SUPPORT_SCORE)
    return best


def _legacy_relation_polarity_matches(
    question: str,
    passage: str,
    polarity: str,
) -> bool:
    opposite = "no" if polarity == "yes" else "yes"
    if not boolean_quote_supports_relation(passage, question, opposite):
        return True
    evidence_negative = bool(
        re.search(
            r"\b(?:doesn't|does not|don't|do not|did not|no|not|never|without|"
            r"cannot|can't|fail(?:ed|s)?|failure|remove(?:d|s)?)\b",
            passage,
            flags=re.IGNORECASE,
        )
    )
    question_negative = bool(
        re.search(
            r"\b(?:doesn't|does not|don't|do not|did not|no|not|never|without|"
            r"downside|disadvantage|drawback|limitation|problem|risk|harm|"
            r"failure)\b",
            question,
            flags=re.IGNORECASE,
        )
    )
    inferred = "yes" if evidence_negative == question_negative else "no"
    return polarity == inferred
