from types import SimpleNamespace

import ktem.reasoning.mara as mara_module
import pytest
from ktem.reasoning.mara import MaraAgentPipeline
from ktem.reasoning.simple import FullQAPipeline


def test_mara_controller_retrieval_uses_request_retrieval_query(monkeypatch):
    seen_queries = []

    class StopAfterRetrieval(RuntimeError):
        pass

    def fake_route_retrieval(
        _pipeline,
        _route,
        query,
        _history,
        _understanding,
        **_kwargs,
    ):
        seen_queries.append(query)
        raise StopAfterRetrieval

    def fake_execute(request, *, retrieve, **_kwargs):
        request.retrieval_query = "revenue 2022"
        retrieve(request, SimpleNamespace(route="doc_text"))

    monkeypatch.setattr(mara_module, "route_retrieval_metadata", fake_route_retrieval)
    monkeypatch.setattr(mara_module, "execute_controller_turn", fake_execute)
    pipeline = MaraAgentPipeline(retrievers=[])

    with pytest.raises(StopAfterRetrieval):
        pipeline.execute_controller_route(
            "What changed?",
            "conv-1",
            [],
            {"modalities": ["text"]},
            {},
            {},
            routing_message="revenue 2021 2022",
        )

    assert seen_queries == ["revenue 2022"]


def test_mara_controller_can_disable_nested_thorough_retry(monkeypatch):
    calls = []

    def empty_retrieve(_self, message, _history):
        calls.append(message)
        return [], []

    monkeypatch.setattr(FullQAPipeline, "retrieve", empty_retrieve)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.agent_mode = "thorough"
    pipeline._mara_disable_nested_retrieval_retry = True

    pipeline.retrieve("missing evidence", [])

    assert len(calls) == 1
