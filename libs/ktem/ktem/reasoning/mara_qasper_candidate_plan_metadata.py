from __future__ import annotations

from typing import Any

from ktem.docqa.canonical_proposition_evidence_plan_contract import (
    canonical_event_identity,
    canonical_predicate_match_kind,
)
from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_lexical import clause_spans

from .mara_qasper_candidate_selector_semantics import revalidated_selector_semantics


def candidate_selector_plan_metadata(
    record: dict[str, Any],
    selector: dict[str, Any],
    question: str,
    semantics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return canonical event/object metadata shared by pack consumers."""

    resolved = semantics or revalidated_selector_semantics(
        selector,
        question,
        str(selector.get("text") or ""),
    )
    analysis = dict(resolved.get("analysis") or {})
    object_tokens = sorted(
        {str(token) for token in analysis.get("covered_object_tokens") or []}
    )
    return {
        "object_tokens": object_tokens,
        "event_id": _selector_event_id(record, selector),
        "event_core_tokens": object_tokens,
        "predicate_match_kind": _predicate_match_kind(question, resolved),
    }


def _selector_event_id(
    record: dict[str, Any],
    selector: dict[str, Any],
) -> str:
    evidence_id = str(record.get("evidence_id") or "")
    record_text = str(record.get("text") or "")
    record_start = int(record.get("text_start") or 0)
    selector_start = int(selector.get("span_start") or 0)
    selector_end = int(selector.get("span_end") or 0)
    local_start = selector_start - record_start
    local_end = selector_end - record_start
    event_start = local_start
    event_end = local_end
    for clause_start, clause_end in clause_spans(record_text):
        if clause_start <= local_start and local_end <= clause_end:
            event_start = clause_start
            event_end = clause_end
            break
    return canonical_event_identity(
        evidence_id,
        record_start + event_start,
        record_start + event_end,
        record_text[event_start:event_end],
    )


def _predicate_match_kind(
    question: str,
    semantics: dict[str, Any],
) -> str:
    proposition = build_question_proposition(question)
    predicate_span = dict(semantics.get("slot_spans") or {}).get("predicate")
    if not isinstance(predicate_span, dict):
        return "missing"
    return canonical_predicate_match_kind(
        proposition,
        str(predicate_span.get("text") or ""),
    )
