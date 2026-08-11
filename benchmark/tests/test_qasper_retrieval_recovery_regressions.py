from __future__ import annotations

from types import SimpleNamespace

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import evaluate_retrieval_quality
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan
from ktem.docqa.query_planning import build_query_plan, missing_slot_requests

from benchmark.docqa_index_cache import DocQAIndexCache, route_requires_element
from benchmark.schemas import BenchmarkDocument

QUESTION = "Did the authors evaluate the model on clinical tasks?"


def _evidence(evidence_id: str, text: str, *, source_id: str = "paper") -> dict:
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "text": text,
    }


def test_qasper_missing_boolean_proposition_gets_one_local_second_round():
    calls: list[tuple[int, str, tuple[str, ...]]] = []

    def retrieve(request, _decision):
        calls.append(
            (
                request.retrieval_round_id,
                request.retrieval_query,
                tuple(request.selected_file_ids or []),
            )
        )
        if request.retrieval_round_id == 1:
            return {"evidence": []}
        return {
            "evidence": [
                _evidence(
                    "support",
                    "We evaluated the model on clinical tasks.",
                    source_id="runtime-file-1",
                )
            ]
        }

    result = execute_controller_turn(
        DocQARequest(
            prompt=QUESTION,
            retrieval_query=QUESTION,
            task_type="boolean",
            verification_domain="qasper",
            route_policy="doc",
            allowed_routes=["doc_text"],
            selected_file_ids=["runtime-file-1"],
        ),
        retrieve=retrieve,
        generate=lambda *_args: "Yes.",
    )

    assert len(calls) == 2
    assert calls[0][0] == 1
    assert calls[1][0] == 2
    assert calls[0][2] == calls[1][2] == ("runtime-file-1",)
    assert calls[1][1] != QUESTION
    assert result.evidence_bundle.metadata["retrieval_rounds"] == 2


def test_unrelated_graph_entity_does_not_satisfy_qasper_boolean_slot():
    plan = build_query_plan(
        QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )
    metadata = {
        "evidence": [
            _evidence(
                "graph-unrelated",
                "The graph entity describes a citation network unrelated to clinical evaluation.",
                source_id="runtime-file-1",
            )
        ],
        "bound_query_plan": plan.as_dict(),
    }

    decision = evaluate_retrieval_quality(
        "hybrid",
        metadata,
        prompt=QUESTION,
        verification_domain="qasper",
    )

    assert decision.status == "ambiguous"
    assert decision.retry is True


def test_non_qasper_verification_only_boolean_slot_stays_out_of_round_two():
    plan = QueryPlan(
        answer_type="boolean",
        question_type="simple_fact",
        evidence_slots=(
            EvidenceSlot(
                slot_id="support:boolean_proposition",
                role="support",
                statement_kind="boolean_proposition",
                required_for_retrieval=False,
                required_for_verification=True,
                query="whether the report confirms the claim",
            ),
        ),
        constraints={"verification_domain": "finance"},
    )

    assert missing_slot_requests(plan) == []
    evidence = _evidence("context", "The report confirms the claim.")
    decision = evaluate_retrieval_quality(
        "doc_text",
        {"evidence": [evidence], "bound_query_plan": plan.as_dict()},
        prompt="Does the report confirm the claim?",
        verification_domain="finance",
    )

    assert decision.status == "good"
    assert decision.retry is False


def test_6f024d4c_true_unanswerable_remains_fail_closed_after_retry():
    calls = 0

    def retrieve(_request, _decision):
        nonlocal calls
        calls += 1
        return {"evidence": []}

    result = execute_controller_turn(
        DocQARequest(
            prompt="What was the baseline?",
            task_type="free_text",
            verification_domain="qasper",
            route_policy="doc",
            allowed_routes=["doc_text"],
            selected_file_ids=["runtime-file-1"],
        ),
        retrieve=retrieve,
        generate=lambda *_args: (_ for _ in ()).throw(
            AssertionError("unanswerable QASPER request must not generate")
        ),
    )

    assert calls == 2
    assert result.retrieve_decision.status == "poor"
    assert result.guardrail_decision.action == "abstain"


def test_auto_route_optional_doc_element_does_not_force_element_index():
    config = SimpleNamespace(
        route="controller_auto",
        route_policy="auto",
        allowed_routes=["doc_text", "doc_element"],
    )

    assert route_requires_element(config) is False
    assert (
        route_requires_element(SimpleNamespace(route="element", route_policy="element"))
        is True
    )
    assert (
        route_requires_element(
            SimpleNamespace(route="doc_element", route_policy="auto")
        )
        is True
    )
    assert (
        route_requires_element(SimpleNamespace(route="hybrid", route_policy="hybrid"))
        is True
    )


def test_cache_identity_partitions_canonical_document_ids(tmp_path):
    path = tmp_path / "paper.txt"
    path.write_text("same paper", encoding="utf-8")
    first = BenchmarkDocument("dataset-paper-a", path, format_type="txt")
    second = BenchmarkDocument("dataset-paper-b", path, format_type="txt")
    cache = DocQAIndexCache(
        SimpleNamespace(suite_name="qasper", route="doc_text"),
        shared_prepared_file_ids={},
    )

    first_key, first_trace = cache.document_identity(first)
    second_key, second_trace = cache.document_identity(second)

    assert first_key != second_key
    assert first_trace["document_id"] == "dataset-paper-a"
    assert second_trace["document_id"] == "dataset-paper-b"
