from __future__ import annotations

import re
from typing import Any

from ktem.docqa.boolean_evidence_scope import classify_boolean_evidence_set

from .qasper_boolean import boolean_quote_supports_relation, stemmed_content_tokens


def resolve_boolean_conflict(
    evidence: str,
    question: str,
    *,
    candidate_polarity: str,
    verdict: str,
    evidence_items: list[dict[str, Any]] | None = None,
) -> tuple[str, str, dict[str, str]]:
    candidate_score = _support_score(
        evidence,
        question,
        candidate_polarity,
        evidence_items=evidence_items,
    )
    opposite = (
        "no" if candidate_polarity == "yes" else "yes" if candidate_polarity else ""
    )
    contradiction_score = _support_score(
        evidence,
        question,
        opposite,
        evidence_items=evidence_items,
    )
    action, answer, conflict_status = _boolean_answer_action(
        candidate_polarity,
        verdict,
        candidate_support_score=candidate_score,
        contradiction_score=contradiction_score,
    )
    return (
        action,
        answer,
        {
            "candidate_support_score": f"{candidate_score:.3f}",
            "contradiction_score": f"{contradiction_score:.3f}",
            "selected_polarity": answer if answer in {"yes", "no"} else "abstain",
            "conflict_status": conflict_status,
            "abstention_reason": conflict_status if answer == "unanswerable" else "",
        },
    )


def _support_score(
    evidence: str,
    question: str,
    polarity: str,
    *,
    evidence_items: list[dict[str, Any]] | None,
) -> float:
    if evidence_items:
        classified = classify_boolean_evidence_set(
            question,
            polarity,
            evidence_items,
        )
        return max(
            (
                assessment.relation_score * assessment.object_score
                for assessment in classified.supports
            ),
            default=0.0,
        )
    return _proposition_support_score(evidence, question, polarity)


def _boolean_answer_action(
    candidate_polarity: str,
    verdict: str,
    *,
    candidate_support_score: float,
    contradiction_score: float,
) -> tuple[str, str, str]:
    if verdict not in {"yes", "no"}:
        if (
            candidate_polarity
            and candidate_support_score > contradiction_score
            and candidate_support_score > 0
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
    if not candidate_polarity:
        return "recovered_boolean_from_abstention", verdict, "none"
    if verdict == candidate_polarity:
        return "confirmed_candidate", verdict, "none"
    if candidate_support_score > contradiction_score:
        return (
            "preserved_candidate_conflict_warning",
            candidate_polarity,
            "candidate_support_dominates",
        )
    if candidate_support_score > 0 and contradiction_score > 0:
        return "abstained_polarity_conflict", "unanswerable", "balanced_conflict"
    return "corrected_polarity", verdict, "opposite_support_only"


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
        negated = bool(
            re.search(
                r"\b(?:doesn't|does not|don't|do not|did not|no|not|never|without)\b",
                passage,
                flags=re.IGNORECASE,
            )
        )
        if (polarity == "no") != negated:
            continue
        if not boolean_quote_supports_relation(passage, question, polarity):
            continue
        passage_tokens = stemmed_content_tokens(passage)
        coverage = len(question_tokens & passage_tokens) / len(question_tokens)
        best = max(best, coverage)
    return best
