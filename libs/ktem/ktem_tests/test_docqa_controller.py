from types import SimpleNamespace

import ktem.docqa as docqa
import pytest
from ktem.docqa._runtime_mara import ResponseCapture, apply_request_context
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import (
    build_controller_outputs,
    evaluate_retrieval_quality,
    parse_planner_decision,
)
from ktem.docqa.execution import execute_controller_turn
from ktem_tests.controller_test_assertions import (
    assert_empty_verify_decision,
    assert_graph_bundle_contract,
)


def test_docqa_package_exports_controller_helpers():
    assert docqa.parse_planner_decision is parse_planner_decision
    assert docqa.evaluate_retrieval_quality is evaluate_retrieval_quality


def test_route_and_executor_registries_expose_evidence_policies():
    routes = docqa.route_registry()
    executors = docqa.executor_registry()

    assert set(routes) == {
        "direct",
        "doc_text",
        "doc_page_image",
        "doc_element",
        "graph_global",
        "hybrid",
        "abstain",
    }
    assert routes["direct"] == {
        "route": "direct",
        "requires_retrieval": False,
        "executor": "direct",
        "evidence_types": [],
        "retrieve_fn": "",
        "generate_fn": "direct_answer",
        "required_evidence_types": [],
        "backend_metadata": {"generator_backend": "local_direct"},
    }
    assert routes["hybrid"] == {
        "route": "hybrid",
        "requires_retrieval": True,
        "executor": "hybrid",
        "evidence_types": ["text", "page_image", "element"],
        "retrieve_fn": "retrieve_hybrid",
        "generate_fn": "generate_docqa_answer",
        "required_evidence_types": ["text", "page_image", "element"],
        "backend_metadata": {
            "text_retriever": "docqa_text",
            "visual_retriever": "local_late_interaction",
            "generator_backend": "local_docqa_generator",
        },
    }
    assert executors["graph_global"] == {
        "route": "graph_global",
        "status": "registered",
        "evidence_types": ["graph"],
    }


def test_response_capture_builds_controller_contract_fields():
    capture = ResponseCapture(
        DocQARequest(
            prompt="How are these sources connected?",
            controller_mode="llm",
            route_policy="graph",
            allowed_routes=["graph_global"],
            verification_mode="strict",
        )
    )
    capture.ingest(
        "debug",
        {
            "mara_channel": "evidence_metadata",
            "payload": {
                "graph_evidence": [
                    {
                        "evidence_id": "doc-1",
                        "id": "doc-1",
                        "label": "Graph Evidence",
                        "summary": "Sources are connected.",
                    }
                ],
                "page_coverage": ["1"],
            },
        },
    )

    payload = capture.as_response_kwargs()

    assert payload["route_decision"] == {
        "route": "graph_global",
        "policy": "graph",
        "controller_mode": "llm",
        "requires_retrieval": True,
        "reason": "Requested graph route.",
    }
    assert payload["retrieve_decision"] == {
        "status": "good",
        "reason": "Retrieved evidence is sufficient for generation.",
        "retry": False,
    }
    assert_empty_verify_decision(
        payload["verify_decision"],
        mode="strict",
        status="supported",
        reason="Strict verification requested; current verifier observed evidence.",
    )
    assert payload["controller_decision"] == {
        "route": "graph_rag",
        "legacy_route": "graph_global",
        "policy": "graph",
        "controller_mode": "llm",
        "requires_retrieval": True,
        "reason": "Requested graph route.",
    }
    assert payload["guardrail_decision"] == {
        "status": "ok",
        "action": "return",
        "reason": "Strict verification requested; current verifier observed evidence.",
    }
    assert payload["controller_trace"][0] == {
        "stage": "planner",
        "controller_mode": "llm",
        "route": "graph_global",
        "policy": "graph",
    }
    assert payload["workflow_plan"]["steps"][0]["executor"] == "retrieve_graph"
    assert_graph_bundle_contract(payload)


def test_apply_request_context_copies_planner_contract_fields():
    pipeline = SimpleNamespace(agent_mode="auto")
    request = DocQARequest(
        prompt="Question",
        planner_model="fake-planner",
        allowed_routes=["hybrid"],
    )

    apply_request_context(pipeline, request, {"related_file_ids": ["file-1"]})

    assert pipeline.planner_model == "fake-planner"
    assert pipeline.allowed_routes == ["hybrid"]
    assert pipeline.graph_context == {"related_file_ids": ["file-1"]}


def test_apply_request_context_uses_heuristic_planner_backend_without_model():
    pipeline = SimpleNamespace(agent_mode="auto")
    request = DocQARequest(
        prompt="Question",
        planner_backend="heuristic_local",
        planner_model="fake-planner",
        allowed_routes=["hybrid"],
    )

    apply_request_context(pipeline, request, {})

    assert pipeline.planner_backend == "heuristic_local"
    assert pipeline.planner_model == ""


@pytest.mark.parametrize(
    ("raw_output", "expected_route", "requires_retrieval"),
    [
        (
            '{"route": "direct", "reason": "Question is conversational."}',
            "direct",
            False,
        ),
        ('{"route": "doc", "reason": "Needs document text."}', "doc_text", True),
        (
            '{"route": "visual", "reason": "Question asks about a figure."}',
            "doc_page_image",
            True,
        ),
        (
            '{"route": "graph", "reason": "Compare themes across files."}',
            "graph_global",
            True,
        ),
        ('{"route": "abstain", "reason": "No source is selected."}', "abstain", False),
    ],
)
def test_parse_planner_decision_accepts_fake_llm_routes(
    raw_output, expected_route, requires_retrieval
):
    decision = parse_planner_decision(raw_output)

    assert decision.route == expected_route
    assert decision.controller_mode == "llm"
    assert decision.requires_retrieval is requires_retrieval


@pytest.mark.parametrize("raw_output", ["not json", "{}", '{"route": "web_search"}'])
def test_invalid_planner_output_uses_safe_doc_text_route(raw_output):
    decision = parse_planner_decision(raw_output)

    assert decision.route == "doc_text"
    assert decision.requires_retrieval is True
    assert decision.reason == "Invalid planner output; using document text route."


def test_response_capture_uses_planner_output_trace_for_llm_auto_route():
    capture = ResponseCapture(
        DocQARequest(prompt="Compare sources.", controller_mode="llm")
    )
    capture.ingest(
        "debug",
        {
            "mara_channel": "agent_trace",
            "payload": {
                "event": "planner_output",
                "decision": {"route": "graph", "reason": "Cross-document compare."},
            },
        },
    )

    payload = capture.as_response_kwargs()

    assert payload["route_decision"]["route"] == "graph_global"
    assert payload["route_decision"]["reason"] == "Cross-document compare."
    assert payload["controller_trace"][0] == {
        "stage": "planner",
        "controller_mode": "llm",
        "route": "graph_global",
        "policy": "auto",
    }
    assert payload["workflow_plan"]["route"] == "graph_global"


def test_retrieval_evaluator_reports_good_ambiguous_and_poor():
    good = evaluate_retrieval_quality(
        "hybrid", {"evidence": [{"evidence_id": "doc-1"}]}
    )
    ambiguous = evaluate_retrieval_quality("hybrid", {"page_coverage": ["1"]})
    poor = evaluate_retrieval_quality("hybrid", {})

    assert good.status == "good"
    assert good.retry is False
    assert ambiguous.status == "ambiguous"
    assert ambiguous.retry is True
    assert poor.status == "poor"
    assert poor.retry is True


def test_retrieval_evaluator_marks_formula_evidence_without_page_as_ambiguous():
    decision = evaluate_retrieval_quality(
        "doc_text",
        {
            "evidence": [
                {
                    "evidence_id": "liquidity-mdna",
                    "text": (
                        "Financial condition and liquidity remained supported by "
                        "strong free cash flow and capital markets access."
                    ),
                }
            ],
            "modality_counts": {"text": 1},
        },
        prompt=(
            "Does 3M have a reasonably healthy liquidity profile based on its "
            "quick ratio for Q2 of FY2023?"
        ),
        verification_domain="finance",
    )

    assert decision.status == "ambiguous"
    assert decision.retry is True


def test_strict_verifier_marks_unsupported_claims_and_abstain_action():
    payload = build_controller_outputs(
        DocQARequest(prompt="Question", verification_mode="strict"),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "doc-1",
                    "file_id": "file-1",
                    "text": "Revenue increased in 2026.",
                }
            ]
        },
        answer="Revenue increased in 2026. Profit declined sharply.",
    )

    assert payload["verify_decision"]["status"] == "unsupported"
    assert payload["verify_decision"]["action"] == "revise"
    assert payload["verify_decision"]["unsupported_claims"] == [
        "Profit declined sharply."
    ]
    assert payload["verify_decision"]["verified_citations"] == ["evidence:file-1:doc-1"]


def test_light_verifier_ignores_reasoning_scaffolding_and_inner_abstain_text():
    payload = build_controller_outputs(
        DocQARequest(prompt="Question", verification_mode="light"),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "doc-1",
                    "file_id": "file-1",
                    "page_label": "2",
                    "text": "Revenue increased in 2026.",
                }
            ]
        },
        answer=(
            "Okay, let's tackle this question. First, I need to recall the "
            "context. Revenue increased in 2026. 文档证据无法支持该回答。"
        ),
    )

    assert payload["verify_decision"]["status"] == "supported"
    assert payload["verify_decision"]["claims"] == ["Revenue increased in 2026."]
    assert payload["guardrail_decision"]["action"] == "return"


def test_direct_route_verification_is_not_required():
    payload = build_controller_outputs(
        DocQARequest(
            prompt="Hello",
            route_policy="direct",
            verification_mode="light",
        ),
        [],
        {},
        answer="Hello.",
    )

    assert payload["retrieve_decision"]["status"] == "not_required"
    assert_empty_verify_decision(
        payload["verify_decision"],
        mode="light",
        status="not_required",
        reason="Direct route does not require evidence verification.",
    )


def test_execute_controller_turn_direct_answer_skips_retrieval_and_generation():
    def fail_retrieve(_request, _decision):
        raise AssertionError("direct_answer must not retrieve")

    def fail_generate(_request, _decision, _bundle):
        raise AssertionError("direct_answer must not generate through RAG")

    result = execute_controller_turn(
        DocQARequest(prompt="Hello", route_policy="direct", verification_mode="strict"),
        retrieve=fail_retrieve,
        generate=fail_generate,
    )

    assert result.controller_decision.route == "direct_answer"
    assert result.guardrail_decision.action == "return"
    assert result.answer
    assert result.evidence_bundle.items == []


def test_execute_controller_turn_poor_retrieval_abstains_before_generation():
    def retrieve(_request, _decision):
        return {}

    def fail_generate(_request, _decision, _bundle):
        raise AssertionError("poor retrieval must not reach generation")

    result = execute_controller_turn(
        DocQARequest(prompt="What does the document say?", route_policy="doc"),
        retrieve=retrieve,
        generate=fail_generate,
    )

    assert result.controller_decision.route == "text_rag"
    assert result.retrieve_decision.status == "poor"
    assert result.guardrail_decision.action == "abstain"
    assert "not retrieve enough evidence" in result.answer


def test_execute_controller_turn_switches_route_after_poor_retrieval():
    calls = []

    def retrieve(_request, decision):
        calls.append(decision.legacy_route)
        if decision.legacy_route == "doc_text":
            return {}
        return {
            "evidence": [
                {
                    "evidence_id": "hybrid-1",
                    "file_id": "file-1",
                    "page_label": "3",
                    "text": "Revenue increased in 2026.",
                }
            ]
        }

    def generate(_request, decision, bundle):
        assert decision.legacy_route == "hybrid"
        assert bundle.items[0]["evidence_id"] == "hybrid-1"
        return "Revenue increased in 2026."

    result = execute_controller_turn(
        DocQARequest(
            prompt="What happened to revenue?",
            route_policy="doc",
            allowed_routes=["doc_text", "hybrid"],
        ),
        retrieve=retrieve,
        generate=generate,
    )

    assert calls == ["doc_text", "hybrid"]
    assert result.controller_decision.legacy_route == "hybrid"
    assert result.retrieve_decision.status == "good"
    assert result.answer == "Revenue increased in 2026."
    assert {
        "route_switch_candidates": [],
        "route_switch_used": False,
    } | result.controller_trace[0] == {
        "stage": "route_switch",
        "from_route": "doc_text",
        "to_route": "hybrid",
        "reason": "No retrieved evidence was captured for this turn.",
        "route_switch_candidates": ["hybrid"],
        "route_switch_used": True,
        "failed_retrieval_rounds": 1,
        "failed_slot_coverage": None,
        "failed_missing_required_slot_count": 0,
    }


def test_execute_controller_turn_retries_ambiguous_retrieval_before_generation():
    calls = []

    def retrieve(_request, _decision):
        calls.append(1)
        if len(calls) == 1:
            return {"page_coverage": ["2"]}
        return {
            "evidence": [
                {
                    "evidence_id": "doc-1",
                    "file_id": "file-1",
                    "page_label": "2",
                    "text": "Revenue increased in 2026.",
                }
            ]
        }

    def generate(_request, _decision, bundle):
        assert bundle.items[0]["evidence_id"] == "doc-1"
        return "Revenue increased in 2026."

    result = execute_controller_turn(
        DocQARequest(prompt="What happened to revenue?", route_policy="doc"),
        retrieve=retrieve,
        generate=generate,
    )

    assert len(calls) == 2
    assert result.retrieve_decision.status == "good"
    assert result.answer == "Revenue increased in 2026."


def test_execute_controller_turn_good_retrieval_generates_with_evidence_bundle():
    def retrieve(_request, _decision):
        return {
            "evidence": [
                {
                    "evidence_id": "doc-1",
                    "file_id": "file-1",
                    "page_label": "2",
                    "text": "Revenue increased in 2026.",
                }
            ]
        }

    def generate(_request, decision, bundle):
        assert decision.route == "text_rag"
        assert bundle.items[0]["evidence_id"] == "doc-1"
        return "Revenue increased in 2026."

    result = execute_controller_turn(
        DocQARequest(
            prompt="What happened to revenue?",
            route_policy="doc",
            verification_mode="strict",
        ),
        retrieve=retrieve,
        generate=generate,
    )

    assert result.answer == "Revenue increased in 2026."
    assert result.guardrail_decision.action == "return"
    assert result.verify_decision.status == "supported"
    assert result.evidence_bundle.items[0]["source_backrefs"] == ["file-1#page:2"]
    assert [
        item["canonical_id"]
        for item in result.evidence_bundle.metadata["verified_evidence"]
    ] == ["evidence:file-1:doc-1"]
    assert [
        item["canonical_id"]
        for item in result.evidence_bundle.metadata["verified_claim_support_evidence"]
    ] == ["evidence:file-1:doc-1"]
    assert "cited_evidence" not in result.evidence_bundle.metadata
    timings = result.evidence_bundle.metadata["pipeline_stage_timings"]
    assert set(timings) == {
        "planning_seconds",
        "retrieval_seconds",
        "generation_seconds",
        "retry_seconds",
        "verification_seconds",
        "finalization_seconds",
    }
    assert all(value >= 0 for value in timings.values())


def test_execute_controller_turn_rewrites_unsupported_answer_once():
    def retrieve(_request, _decision):
        return {
            "evidence": [
                {
                    "evidence_id": "doc-1",
                    "file_id": "file-1",
                    "page_label": "2",
                    "text": "Revenue increased in 2026.",
                }
            ]
        }

    def generate(_request, _decision, _bundle):
        return "Profit declined sharply."

    rewrite_calls = []

    def rewrite(_request, _decision, _bundle, _answer):
        rewrite_calls.append(1)
        return "Revenue increased in 2026."

    result = execute_controller_turn(
        DocQARequest(
            prompt="What happened to revenue?",
            route_policy="doc",
            verification_mode="strict",
        ),
        retrieve=retrieve,
        generate=generate,
        rewrite=rewrite,
    )

    assert len(rewrite_calls) == 1
    assert result.answer == "Revenue increased in 2026."
    assert result.guardrail_decision.action == "return"


def test_execute_controller_turn_element_route_requires_element_evidence():
    def retrieve(_request, _decision):
        return {
            "evidence": [
                {
                    "evidence_id": "text-1",
                    "file_id": "file-1",
                    "page_label": "2",
                    "text": "Table-like paragraph.",
                }
            ]
        }

    def generate(_request, decision, _bundle):
        assert decision.legacy_route == "doc_text"
        return "The table-like paragraph identifies revenue."

    result = execute_controller_turn(
        DocQARequest(prompt="Which table shows revenue?", route_policy="element"),
        retrieve=retrieve,
        generate=generate,
    )

    assert "not retrieve enough evidence" in result.answer
    assert result.controller_decision.route == "element_rag"
    assert result.retrieve_decision.status == "poor"
    assert result.guardrail_decision.action == "abstain"
    assert result.evidence_bundle.metadata["missing_required_slot_count"] == 1
