import time
from time import monotonic
from types import SimpleNamespace

import ktem.reasoning.mara_route_preparation as route_preparation
from ktem.docqa._runtime_models import DocQARequest
from ktem.reasoning.mara import MaraAgentPipeline


def test_mara_route_probe_deadline_commits_typed_abstention(monkeypatch):
    def slow_probe(*_args, **_kwargs):
        time.sleep(0.3)
        return {}

    monkeypatch.setattr(route_preparation, "controller_route_probe", slow_probe)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.route_deadline_monotonic = monotonic() + 0.1
    pipeline.route_terminal_reserve_seconds = 0.02
    started = monotonic()

    events = list(pipeline.stream("What does the paper report?", "conv-1", []))

    assert monotonic() - started < 0.2
    [execution] = [
        event.content["payload"]
        for event in events
        if event.channel == "debug" and event.content.get("mara_channel") == "execution"
    ]
    assert execution["engine_terminal_answer"] == "unanswerable"
    assert execution["engine_terminal_commit"]["answer_status"] == "abstained"
    assert execution["verify_decision"]["reason"] == "route_deadline_exhausted"
    assert execution["guardrail_decision"]["action"] == "abstain"
    deadline = [
        event
        for event in execution["controller_trace"]
        if event.get("stage") == "route_deadline"
    ][-1]
    assert deadline["blocking_stage"] == "route_probe"


def test_qasper_route_probe_uses_unmodified_initial_question(monkeypatch):
    question = "Do the authors conduct experiments on the dataset?"
    captured: list[str] = []

    def probe(_pipeline, query, _history, _understanding):
        captured.append(query)
        return {}

    monkeypatch.setattr(route_preparation, "controller_route_probe", probe)
    pipeline = SimpleNamespace(
        controller_mode="llm",
        route_policy="auto",
        allowed_routes=["doc_text", "hybrid"],
        planner=None,
        planner_model=None,
        verification_domain="qasper",
    )
    request = DocQARequest(
        prompt=question,
        controller_question=question,
        retrieval_query=question,
        task_type="boolean",
        verification_domain="qasper",
    )

    preparation = route_preparation.prepare_controller_route(
        pipeline,
        request,
        question,
        [],
        {
            "question": question,
            "task_type": "qa",
            "modalities": ["text"],
            "available_modalities": ["text"],
            "scope": "document",
        },
        {"event": "route"},
    )

    assert preparation.deadline_execution is None
    assert captured == [question]
