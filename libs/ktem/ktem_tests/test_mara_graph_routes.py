import json

import ktem.reasoning.mara as mara_module
from ktem.reasoning.mara import MARA_ABSTAIN_MESSAGE, MaraAgentPipeline
from ktem.reasoning.mara_graph import build_graph_route_result
from ktem.reasoning.simple import FullQAPipeline


def _fail_if_text_rag_runs(route_name: str):
    def fail(_self, _message, _conv_id, _history, **_kwargs):
        raise AssertionError(f"{route_name} route should not call text RAG")
        yield

    return fail


def test_graph_planner_without_graph_context_falls_back_and_abstains(monkeypatch):
    monkeypatch.setattr(FullQAPipeline, "stream", _fail_if_text_rag_runs("Graph"))
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner = lambda _payload: json.dumps(
        {"route": "graph", "reason": "Needs graph index."}
    )
    pipeline.graph_context = {}

    events = list(pipeline.stream("Compare the source themes.", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        MARA_ABSTAIN_MESSAGE
    ]
    trace_events = [
        event.content["payload"]
        for event in events
        if event.channel == "debug"
        and event.content.get("mara_channel") == "agent_trace"
    ]
    planner_event = next(
        event for event in trace_events if event.get("event") == "planner_output"
    )
    assert planner_event["decision"]["planner_route"] == "graph_global"
    assert planner_event["decision"]["route"] == "doc_text"
    assert any(
        event.get("event") == "guardrail"
        and event.get("route") == "text_rag"
        and event.get("action") == "abstain"
        for event in trace_events
    )


def test_mara_graph_route_without_graph_summary_abstains_before_text_rag(monkeypatch):
    monkeypatch.setattr(FullQAPipeline, "stream", _fail_if_text_rag_runs("Graph"))
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner = lambda _payload: json.dumps(
        {"route": "graph", "reason": "Needs graph index."}
    )
    pipeline.graph_context = {
        "node_id": "theme-1",
        "label": "Revenue",
        "support_pages": {"file-a": ["2"]},
    }

    events = list(pipeline.stream("Compare source themes.", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        MARA_ABSTAIN_MESSAGE
    ]


def test_graph_route_uses_local_graph_index_evidence():
    result = build_graph_route_result(
        {"decision": {"route": "graph_global"}},
        {
            "graph_index": {
                "community_summaries": [
                    {
                        "id": "community-1",
                        "label": "Revenue System",
                        "summary": "Revenue metrics connect report A and report B.",
                        "source_backrefs": ["file-a#page:2", "file-b#page:5"],
                    }
                ],
                "entities": [
                    {
                        "id": "entity-1",
                        "label": "Revenue",
                        "summary": "Revenue appears in both reports.",
                        "source_backrefs": ["file-a#page:2"],
                    }
                ],
                "relations": [
                    {
                        "id": "relation-1",
                        "source": "Revenue",
                        "target": "Growth",
                        "description": "Revenue is tied to growth.",
                        "source_backrefs": ["file-b#page:5"],
                    }
                ],
                "claims": [
                    {
                        "id": "claim-1",
                        "text": "Revenue increased in both reports.",
                        "source_backrefs": ["file-a#page:2"],
                    }
                ],
            }
        },
        {"question": "Compare the revenue system across reports."},
    )

    assert result is not None
    assert "Revenue metrics connect report A and report B" in result.answer
    assert result.evidence_metadata["graph_backend"] == "local_graph_index"
    assert result.evidence_metadata["graph_evidence"][0]["evidence_id"] == (
        "graph-community:community-1"
    )
    assert result.evidence_metadata["graph_evidence"][0]["source_backrefs"] == [
        "file-a#page:2",
        "file-b#page:5",
    ]


def test_mara_graph_route_uses_graph_index_without_text_rag(monkeypatch):
    monkeypatch.setattr(FullQAPipeline, "stream", _fail_if_text_rag_runs("Graph"))
    execute_calls = []
    original_execute = mara_module.execute_controller_turn

    def capture_execute(*args, **kwargs):
        execute_calls.append((args, kwargs))
        return original_execute(*args, **kwargs)

    monkeypatch.setattr(mara_module, "execute_controller_turn", capture_execute)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner = lambda _payload: json.dumps(
        {"route": "graph", "reason": "Needs graph index."}
    )
    pipeline.graph_context = {
        "graph_index": {
            "community_summaries": [
                {
                    "id": "community-1",
                    "label": "Revenue System",
                    "summary": "Revenue metrics connect report A and report B.",
                    "source_backrefs": ["file-a#page:2", "file-b#page:5"],
                }
            ]
        }
    }

    events = list(pipeline.stream("Compare revenue across reports.", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        "Revenue metrics connect report A and report B."
    ]
    assert len(execute_calls) == 1
