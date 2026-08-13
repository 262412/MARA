import json
from types import SimpleNamespace

import ktem.reasoning.mara as mara_module
import pytest
from ktem.reasoning.mara import MaraAgentPipeline
from ktem.reasoning.mara_controller_request import controller_execution_request
from ktem.reasoning.simple import FullQAPipeline

from kotaemon.base import Document, RetrievedDocument


def test_controller_request_propagates_answer_type_for_query_planning():
    pipeline = SimpleNamespace(
        task_type="numeric",
        dataset_family="finance",
        controller_question="What was the percentage change?",
        retrieval_query="percentage change",
        docqa_request=SimpleNamespace(
            origin="benchmark",
            generation_temperature=0,
            generation_top_p=1,
            generation_seed=20260724,
        ),
    )

    request = controller_execution_request(pipeline, "Generate the final answer.")

    assert request.task_type == "numeric"
    assert request.answer_type == "numeric"
    assert request.generation_temperature == 0
    assert request.generation_top_p == 1
    assert request.generation_seed == 20260724


def _fake_answer_stream(_self, _message, _conv_id, _history, **_kwargs):
    yield Document(channel="chat", content="grounded answer")
    return Document(channel="chat", content="grounded answer")


@pytest.mark.parametrize(
    ("route_policy", "controller_mode", "agent_mode"),
    (
        ("doc", "off", "fast"),
        ("auto", "llm", "fast"),
        ("auto", "llm", "thorough"),
    ),
    ids=("text_rag", "controller_auto", "crag_guarded"),
)
def test_mara_stream_preserves_agent_mode_in_authoritative_controller_request(
    monkeypatch,
    route_policy: str,
    controller_mode: str,
    agent_mode: str,
):
    captured = {}
    original_execute = mara_module.execute_controller_turn

    def capture_execute(request, **kwargs):
        result = original_execute(request, **kwargs)
        captured["request"] = request
        captured["result"] = result
        return result

    monkeypatch.setattr(FullQAPipeline, "stream", _fake_answer_stream)
    monkeypatch.setattr(mara_module, "execute_controller_turn", capture_execute)

    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.route_policy = route_policy
    pipeline.controller_mode = controller_mode
    pipeline.agent_mode = agent_mode
    pipeline.verification_mode = "off"
    pipeline.planner = lambda _payload: json.dumps(
        {"route": "doc", "reason": "Needs document text."}
    )
    monkeypatch.setattr(
        pipeline,
        "retrieve",
        lambda _message, _history: (
            [
                RetrievedDocument(
                    text="Document evidence.",
                    id_="doc-1",
                    metadata={"file_id": "file-1", "page_label": "1"},
                )
            ],
            [],
        ),
    )

    events = list(pipeline.stream("What changed?", "conv-1", []))

    route_events = [
        event.content["payload"]
        for event in events
        if event.channel == "debug"
        and event.content.get("mara_channel") == "agent_trace"
        and event.content["payload"].get("event") == "route"
    ]
    assert route_events[0]["agent_mode"] == agent_mode
    assert captured["request"].agent_mode == agent_mode
    assert captured["result"].workflow_plan["agent_mode"] == agent_mode
