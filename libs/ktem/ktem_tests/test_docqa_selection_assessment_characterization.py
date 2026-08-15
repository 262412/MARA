from __future__ import annotations

from collections import Counter
from typing import Any

import ktem.docqa.boolean_proposition_candidates as candidate_module
import ktem.docqa.boolean_proposition_evidence as proposition_module
from ktem.docqa.evidence_set_selection import select_evidence_for_plan
from ktem.docqa.query_planning import build_query_plan


QUESTION = "Did the authors release source code?"


def _items() -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": "support",
            "source_id": "paper",
            "section_id": "methods",
            "page_label": "1",
            "text": "We release source code for the toolkit.",
            "reranker_score": 0.2,
        },
        {
            "evidence_id": "related",
            "source_id": "paper",
            "section_id": "related_work",
            "page_label": "2",
            "text": "Previous work released source code for a toolkit.",
            "reranker_score": 0.9,
        },
        {
            "evidence_id": "noise",
            "source_id": "paper",
            "section_id": "results",
            "page_label": "3",
            "text": (
                "We evaluate the toolkit on three datasets. "
                + "The evaluation protocol reports several unrelated results. " * 30
            ),
            "reranker_score": 0.8,
        },
    ]


def test_boolean_candidate_assessment_is_once_per_slot_identity_and_revision(
    monkeypatch: Any,
) -> None:
    calls: Counter[tuple[str, str, str]] = Counter()
    original = proposition_module.classify_boolean_evidence_candidates

    def counted(
        question: str,
        answer: str,
        item: dict[str, Any],
    ) -> Any:
        calls[
            (
                " ".join(question.casefold().split()),
                str(item.get("evidence_id") or ""),
                str(item.get("text") or ""),
            )
        ] += 1
        return original(question, answer, item)

    monkeypatch.setattr(
        proposition_module,
        "classify_boolean_evidence_candidates",
        counted,
    )
    monkeypatch.setattr(
        candidate_module,
        "classify_boolean_evidence_candidates",
        counted,
    )

    plan = build_query_plan(
        QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )
    selected, trace, bound = select_evidence_for_plan(QUESTION, _items(), plan)

    assert sum(calls.values()) == 3
    assert {key[1] for key in calls} == {"support", "related", "noise"}
    assert set(calls.values()) == {1}
    assert [item["evidence_id"] for item in selected] == [
        "support",
        "related",
        "noise",
    ]
    [slot] = bound.evidence_slots
    assert slot.status == "retrieved_unverified"
    assert slot.evidence_ids == ("evidence:paper:support",)
    assert trace["candidate_count"] == 3
    assert trace["selected_count"] == 3
    assert trace["required_slot_candidates_restored"] == 0
    assert trace["trace_validation_errors"] == []
    assert trace["required_slot_bindings"] == [
        {
            "slot_id": "support:boolean_proposition",
            "status": "retrieved_unverified",
            "retrieval_satisfied": True,
            "execution_satisfied": None,
            "verification_satisfied": False,
            "reason": "",
            "selected_evidence_ids": ["evidence:paper:support"],
            "best_selected_slot_score": 3.25,
            "candidate_selection_reasons": [
                {
                    "evidence_id": "evidence:paper:support",
                    "reason": "bound_to_slot",
                    "slot_score": 3.25,
                }
            ],
            "candidate_drop_reasons": [
                {
                    "evidence_id": "evidence:paper:related",
                    "reason": "semantic_slot_mismatch",
                    "slot_score": 0.0,
                },
                {
                    "evidence_id": "evidence:paper:noise",
                    "reason": "semantic_slot_mismatch",
                    "slot_score": 0.0,
                },
            ],
        }
    ]
    assert [row["evidence_id"] for row in trace["evidence_stage_trace"]] == [
        "evidence:paper:related",
        "evidence:paper:noise",
        "evidence:paper:support",
    ]

