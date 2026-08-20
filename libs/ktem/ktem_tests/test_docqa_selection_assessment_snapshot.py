from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

import ktem.docqa.boolean_proposition_candidates as candidate_module
import ktem.docqa.boolean_proposition_evidence as proposition_module
import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_proposition_evidence import boolean_proposition_authority_level
from ktem.docqa.evidence import build_evidence_bundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_set_objective import marginal_set_gain
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_evidence_binding_support import score_evidence_for_slot
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.selection_assessment_snapshot import (
    SelectionAssessmentCacheMiss,
    SelectionAssessmentSnapshot,
    semantic_assessment_key,
)

QUESTION = "Did the authors release source code?"


def _item(
    evidence_id: str,
    text: str,
    *,
    section_id: str,
    score: float,
    source_id: str = "runtime-source-A",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "section_id": section_id,
        "page_label": evidence_id,
        "text": text,
        "metadata": {
            "reranker_input_identity": f"raw:{evidence_id}",
            "reranker_score": score,
        },
    }


def _items() -> list[dict[str, Any]]:
    return [
        _item(
            "support",
            "We release source code for the toolkit.",
            section_id="methods",
            score=0.2,
        ),
        _item(
            "related",
            "Previous work released source code for a toolkit.",
            section_id="related_work",
            score=0.9,
        ),
        _item(
            "noise",
            "We evaluate the toolkit on three datasets. "
            + "The evaluation protocol reports unrelated results. " * 40,
            section_id="results",
            score=0.8,
        ),
        _item(
            "future",
            "We plan to release source code in future work.",
            section_id="future_work",
            score=0.7,
        ),
        _item(
            "method",
            "Our method uses a public benchmark and open data.",
            section_id="methods",
            score=0.6,
        ),
        _item(
            "result",
            "The toolkit improves accuracy on the benchmark.",
            section_id="results",
            score=0.5,
        ),
    ]


def _reranker_trace(items: list[dict[str, Any]]) -> dict[str, Any]:
    output_order = ("related", "noise", "future", "method", "result", "support")
    return {
        "configured": True,
        "loaded": True,
        "executed": True,
        "backend": "tei",
        "model": "bge",
        "query_id": "q:boolean",
        "slot_id": "support:boolean_proposition",
        "round_id": 1,
        "input_count": len(items),
        "output_count": len(items),
        "scored_count": len(items),
        "input_identities": [f"raw:{item['evidence_id']}" for item in items],
        "output_identities": [f"raw:{value}" for value in output_order],
        "score_field": "reranker_score",
    }


def _request() -> DocQARequest:
    return DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        selected_file_ids=["paper"],
        origin="benchmark",
    )


def _count_classifications(monkeypatch: Any) -> Counter[str]:
    calls: Counter[str] = Counter()
    original = proposition_module.classify_boolean_evidence_candidates

    def counted(
        question: str,
        answer: str,
        item: dict[str, Any],
    ) -> Any:
        calls[str(item.get("evidence_id") or "")] += 1
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
    return calls


def test_real_reranker_trace_reuses_one_boolean_assessment_snapshot(
    monkeypatch: Any,
) -> None:
    items = _items()
    calls = _count_classifications(monkeypatch)

    reranker_trace = _reranker_trace(items)
    bundle = build_evidence_bundle(
        "doc_text",
        _request(),
        {
            "evidence": items,
            "reranker_execution_traces": [reranker_trace],
        },
    )

    assert [item["evidence_id"] for item in bundle.items] == [
        "support",
        "related",
        "future",
    ]
    assert [item["evidence_id"] for item in bundle.metadata["reranked_evidence"]] == [
        "related",
        "noise",
        "future",
        "method",
        "result",
        "support",
    ]
    assert all(
        len(item.get("reranker_observations") or []) == 1
        for item in bundle.metadata["reranked_evidence"]
    )
    assert bundle.metadata["reranker_execution_traces"] == [reranker_trace]
    assert sum(calls.values()) == len(items)
    assert set(calls.values()) == {1}
    audit = bundle.metadata["boolean_assessment_cache"]
    assert audit["unique_semantic_candidates"] == len(items)
    assert audit["slots"] == 1
    assert audit["cache_builds"] == 1
    assert audit["classification_calls"] == len(items)
    assert audit["cache_hits"] > len(items)
    assert audit["cache_misses"] == 0
    assert audit["mmr_hot_loop_misses"] == 0
    assert audit["time_spent_ms"] >= 0.0
    assert (
        bundle.metadata["evidence_selection_trace"]["boolean_assessment_cache"] == audit
    )


def test_semantic_key_ignores_runtime_and_reranker_identity_fields() -> None:
    plan = build_query_plan(
        QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )
    [slot] = plan.evidence_slots
    base = _items()[0]
    decorated = deepcopy(base)
    decorated.update(
        {
            "source_id": "runtime-source-B",
            "runtime_source_id": "uuid-B",
            "evaluation_source_id": "dataset-row-B",
            "score": 0.999,
            "rank": 1,
            "raw_rank": 1,
            "retrieval_rank": 1,
            "reranker_rank": 1,
            "reranker_observations": [{"rank": 1, "score": 0.999}],
            "retrieval_lineage": [{"route": "hybrid", "raw_rank": 1}],
            "route": "hybrid",
            "trace": {"query_id": "volatile"},
            "source_name": "presentation-only.pdf",
            "source_backrefs": ["runtime-source-B#page:1"],
            "representations": [{"modality": "text", "text": "rendered copy"}],
            "bbox": [0, 0, 10, 10],
            "_selection_relevance_score": 1.0,
            "presentation_metadata": {"color": "blue"},
        }
    )
    decorated["metadata"].update(
        {
            "source_id": "runtime-source-B",
            "runtime_source_id": "uuid-B",
            "reranker_input_identity": "raw:other",
            "reranker_score": 0.999,
            "reranker_rank": 1,
            "reranker_observations": [{"rank": 1, "score": 0.999}],
            "rank": 1,
            "raw_rank": 1,
            "retrieval_rank": 1,
            "retrieval_lineage": [{"route": "hybrid"}],
            "route": "hybrid",
            "trace": {"query_id": "volatile"},
        }
    )

    assert semantic_assessment_key(plan, slot, base) == semantic_assessment_key(
        plan,
        slot,
        decorated,
    )

    changed_text = deepcopy(decorated)
    changed_text["text"] = "We do not release source code for the toolkit."
    assert semantic_assessment_key(plan, slot, base) != semantic_assessment_key(
        plan,
        slot,
        changed_text,
    )

    changed_scope = deepcopy(decorated)
    changed_scope["section_id"] = "future_work"
    assert semantic_assessment_key(plan, slot, base) != semantic_assessment_key(
        plan,
        slot,
        changed_scope,
    )


def test_semantic_cache_identity_does_not_replace_output_identity(
    monkeypatch: Any,
) -> None:
    plan = build_query_plan(
        QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )
    calls = _count_classifications(monkeypatch)
    left = _item(
        "shared-local-id",
        "We release source code for the toolkit.",
        section_id="methods",
        score=0.9,
        source_id="runtime-source-A",
    )
    right = deepcopy(left)
    right["source_id"] = "runtime-source-B"
    snapshot = SelectionAssessmentSnapshot.build(plan, [left, right])
    [slot] = plan.evidence_slots

    assert snapshot.candidate_score(plan, slot, left) == snapshot.candidate_score(
        plan,
        slot,
        right,
    )
    assert identity_of(left).key != identity_of(right).key
    assert sum(calls.values()) == 1
    assert snapshot.audit()["unique_semantic_candidates"] == 1
    assert snapshot.audit()["cache_entries"] == 1


def test_snapshot_authority_remains_independent_from_candidate_relevance() -> None:
    plan = build_query_plan(
        QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )
    items = _items()
    snapshot = SelectionAssessmentSnapshot.build(plan, items)
    [slot] = plan.evidence_slots

    for item in items:
        assert snapshot.authority_level(plan, slot, item) == (
            boolean_proposition_authority_level(slot.query or slot.metric, item)
        )


@pytest.mark.parametrize(
    ("question", "evidence", "section_id"),
    (
        (
            "Do they use off-the-shelf NLP systems to build their assistant?",
            (
                "Natural Language Understanding (NLU): We implemented an NLU "
                "unit utilizing handcrafted rules, Regular Expressions (RegEx) "
                "and Elasticsearch (ES) API."
            ),
            "methods",
        ),
        (
            "Does BERT reach the best performance among all the algorithms compared?",
            (
                "BERT remains 0.3 F1-score points behind the winning system and "
                "would have achieved the second position among all competitors."
            ),
            "results",
        ),
    ),
)
def test_boolean_slot_authority_uses_lossless_query_not_normalized_metric(
    question: str,
    evidence: str,
    section_id: str,
) -> None:
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )
    item = _item(
        "structured-authority",
        evidence,
        section_id=section_id,
        score=0.9,
    )
    [slot] = plan.evidence_slots
    snapshot = SelectionAssessmentSnapshot.build(plan, [item])

    assert slot.query == question
    assert snapshot.candidate_score(plan, slot, item) > 0
    assert snapshot.authority_level(plan, slot, item) == "complete"
    assert score_evidence_for_slot(slot, item) == 0
    bound = bind_evidence_slots(plan, [item], assessments=snapshot)
    [bound_slot] = bound.evidence_slots
    assert bound_slot.status == "retrieved_unverified"
    assert bound_slot.evidence_ids == (identity_of(item).key,)


def test_snapshot_expands_only_truly_new_semantic_candidate(
    monkeypatch: Any,
) -> None:
    plan = build_query_plan(
        QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )
    calls = _count_classifications(monkeypatch)
    initial = _items()[:2]
    snapshot = SelectionAssessmentSnapshot.build(plan, initial)
    reranked = deepcopy(initial)
    for rank, item in enumerate(reranked, start=1):
        item["source_id"] = f"reranked-runtime-{rank}"
        item["reranker_observations"] = [{"rank": rank, "score": 1 / rank}]
    new_candidate = _items()[2]

    expanded = snapshot.expanded(plan, [*reranked, new_candidate])
    unchanged = expanded.expanded(plan, list(reversed([*reranked, new_candidate])))

    assert sum(calls.values()) == 3
    assert set(calls.values()) == {1}
    assert unchanged is expanded
    assert expanded.audit()["cache_builds"] == 2
    assert expanded.audit()["classification_calls"] == 3
    assert expanded.audit()["unique_semantic_candidates"] == 3


def test_hot_loop_cache_miss_is_explicit_and_never_reclassifies(
    monkeypatch: Any,
) -> None:
    plan = build_query_plan(
        QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )
    calls = _count_classifications(monkeypatch)
    first, second = _items()[:2]
    snapshot = SelectionAssessmentSnapshot.build(plan, [first])

    with pytest.raises(SelectionAssessmentCacheMiss):
        marginal_set_gain(
            second,
            [],
            plan,
            assessments=snapshot,
            hot_loop=True,
        )

    assert sum(calls.values()) == 1
    assert snapshot.audit()["cache_misses"] == 1
    assert snapshot.audit()["mmr_hot_loop_misses"] == 1


def test_non_boolean_finance_plan_has_no_candidate_slot_prebuild() -> None:
    plan = build_query_plan(
        "What percentage of 2021 net sales came from Europe?",
        answer_type="numeric",
        verification_domain="financebench",
    )
    candidates = [
        {
            "source_id": "finance-runtime",
            "cell_id": f"cell-{index}",
            "text": f"Europe net sales row {index}",
            "value": str(index),
            "period": "2021",
        }
        for index in range(200)
    ]

    snapshot = SelectionAssessmentSnapshot.build(plan, candidates)

    assert snapshot.audit() == {
        "unique_semantic_candidates": 0,
        "slots": 0,
        "cache_entries": 0,
        "cache_builds": 1,
        "cache_hits": 0,
        "cache_misses": 0,
        "classification_calls": 0,
        "mmr_hot_loop_misses": 0,
        "time_spent_ms": 0.0,
    }
