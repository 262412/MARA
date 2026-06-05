import ktem.docqa as docqa
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.workflow import build_workflow_plan


def test_executor_registry_exposes_workflow_agents():
    executors = docqa.executor_registry()

    assert executors["query_reformulator"] == {
        "executor": "query_reformulator",
        "role": "planner_support",
        "status": "registered",
        "routes": [
            "doc_text",
            "doc_page_image",
            "doc_element",
            "graph_global",
            "hybrid",
        ],
        "cost_units": 1,
    }
    assert executors["fuse_evidence"]["role"] == "evidence_fusion"


def test_build_workflow_plan_accepts_planner_multi_step_workflow():
    plan = build_workflow_plan(
        route="hybrid",
        request=DocQARequest(
            prompt="Compare table and chart evidence.",
            controller_mode="llm",
            verification_mode="strict",
        ),
        planner_payload={
            "route": "hybrid",
            "workflow": [
                {"executor": "query_reformulator", "reason": "Normalize query."},
                {"executor": "retrieve_text", "route": "doc_text"},
                {"executor": "retrieve_page_image", "route": "doc_page_image"},
                {"executor": "fuse_evidence"},
                {"executor": "generate_docqa_answer"},
                {"executor": "verify_answer"},
            ],
        },
        policy="auto",
        controller_mode="llm",
    ).as_dict()

    assert plan["strategy"] == "planner_workflow"
    assert plan["total_cost_units"] == 8
    assert plan["reward_features"] == {
        "cost_units": 8,
        "quality_signal": "verification_status",
    }
    assert [
        (step["executor"], step["route"], step["role"], step["cost_units"])
        for step in plan["steps"]
    ] == [
        ("query_reformulator", "hybrid", "planner_support", 1),
        ("retrieve_text", "doc_text", "retriever", 1),
        ("retrieve_page_image", "doc_page_image", "retriever", 2),
        ("fuse_evidence", "hybrid", "evidence_fusion", 1),
        ("generate_docqa_answer", "hybrid", "generator", 2),
        ("verify_answer", "hybrid", "verifier", 1),
    ]


def test_build_workflow_plan_defaults_graph_route_to_local_global_sequence():
    plan = build_workflow_plan(
        route="graph_global",
        request=DocQARequest(
            prompt="Summarize cross-document themes.",
            route_policy="graph",
            verification_mode="strict",
        ),
        policy="graph",
        controller_mode="off",
    )

    assert [step["executor"] for step in plan.as_dict()["steps"]] == [
        "retrieve_graph",
        "generate_graph_summary",
        "verify_answer",
    ]
    assert plan.strategy == "route_default"


def test_execute_controller_turn_records_workflow_plan_and_trace():
    def retrieve(_request, _decision):
        return {
            "evidence": [
                {
                    "evidence_id": "doc-1",
                    "file_id": "file-1",
                    "page_label": "1",
                    "text": "Revenue increased in 2026.",
                }
            ]
        }

    def generate(_request, decision, _bundle):
        assert decision.legacy_route == "hybrid"
        return "Revenue increased in 2026."

    result = execute_controller_turn(
        DocQARequest(prompt="Use text and visual evidence.", controller_mode="llm"),
        retrieve=retrieve,
        generate=generate,
        agent_trace=[
            {
                "event": "planner_output",
                "decision": {
                    "route": "hybrid",
                    "workflow": [
                        {"executor": "retrieve_text", "route": "doc_text"},
                        {"executor": "retrieve_page_image", "route": "doc_page_image"},
                        {"executor": "fuse_evidence"},
                        {"executor": "generate_docqa_answer"},
                    ],
                },
            }
        ],
    )

    assert result.workflow_plan["strategy"] == "planner_workflow"
    assert [step["executor"] for step in result.workflow_plan["steps"]] == [
        "retrieve_text",
        "retrieve_page_image",
        "fuse_evidence",
        "generate_docqa_answer",
    ]
    assert result.controller_trace[1] == {
        "stage": "workflow_plan",
        "strategy": "planner_workflow",
        "step_count": 4,
        "total_cost_units": 6,
    }
