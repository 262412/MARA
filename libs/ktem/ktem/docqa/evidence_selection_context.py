from __future__ import annotations

from typing import Any

from .evidence_identity import identity_of
from .query_planning import QueryPlan, retrieval_budget
from .required_slot_selection import (
    required_slot_candidate_limit,
    required_slot_shortlist,
)
from .selection_assessment_table import SelectionAssessmentTable
from .selection_score_normalization import normalized_selection_scores

RERANK_CANDIDATE_LIMIT = 30


def evidence_selection_context(
    items: list[dict[str, Any]],
    plan: QueryPlan,
    assessments: SelectionAssessmentTable,
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    candidates, restored_required = required_slot_shortlist(
        items,
        plan,
        candidate_limit=required_slot_candidate_limit(
            plan,
            base_limit=RERANK_CANDIDATE_LIMIT,
        ),
        assessments=assessments,
    )
    return (
        normalized_selection_scores(
            candidates,
            identity_of=lambda item: identity_of(item).key,
        ),
        restored_required,
        retrieval_budget(plan),
    )
