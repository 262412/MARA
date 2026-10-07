"""The Runtime response cache must retain the authenticated request principal."""

from types import SimpleNamespace
from typing import Any, cast

import pytest
from ktem.db.models import Conversation
from ktem.docqa import runtime as runtime_module
from ktem.docqa.runtime import DocQARuntime
from sqlmodel import Session

from . import test_graph_cache_interleavings as fixtures

graph_store = fixtures.graph_store
build = fixtures.build


def _runtime(store, service, user, monkeypatch):
    monkeypatch.setattr(runtime_module, "engine", store.engine)
    runtime = cast(Any, object.__new__(DocQARuntime))
    runtime._user_id = user
    runtime._app = SimpleNamespace(index_manager=SimpleNamespace(indices=[]))
    runtime.file_index = service._index
    runtime.knowledge_graph = service
    return runtime


def test_runtime_owner_reads_current_cache_without_rebuilding(graph_store, monkeypatch):
    service = graph_store.service()
    build(graph_store, service, ["a"])
    expected = service._load_cached_state("conv")
    before = service._get_storage_path("conv").read_bytes()
    runtime = _runtime(graph_store, service, "owner", monkeypatch)
    assert runtime.get_conversation_graph_cache("conv") == expected
    assert expected["graph"] and set(expected["manifest"]) == {"a"}
    assert service._get_storage_path("conv").read_bytes() == before


def test_runtime_cache_read_refuses_reindexed_source_until_rebuilt(
    graph_store, monkeypatch
):
    service = graph_store.service()
    build(graph_store, service, ["a"])
    runtime = _runtime(graph_store, service, "owner", monkeypatch)
    before = service._get_storage_path("conv").read_bytes()
    with Session(graph_store.engine) as session:
        session.add(
            graph_store.Index(
                source_id="a", target_id="replacement", relation_type="document"
            )
        )
        session.commit()
    assert runtime.get_conversation_graph_cache("conv") is None
    assert service._get_storage_path("conv").read_bytes() == before
    build(graph_store, service, ["a"])
    assert runtime.get_conversation_graph_cache("conv") == service._load_cached_state(
        "conv"
    )


def test_runtime_cache_read_rejects_replacement_between_load_and_lease(
    graph_store, monkeypatch
):
    service = graph_store.service()
    newer = graph_store.service()
    build(graph_store, service, ["a"])
    runtime = _runtime(graph_store, service, "owner", monkeypatch)
    original = service._load_cached_state
    reads = []

    def load_then_replace(conversation_id):
        state = original(conversation_id)
        reads.append(state)
        if len(reads) == 1:
            build(graph_store, newer, ["b"])
        return state

    monkeypatch.setattr(service, "_load_cached_state", load_then_replace)
    assert runtime.get_conversation_graph_cache("conv") is None
    assert len(reads) == 2 and reads[0] != reads[1]
    assert set(newer._load_cached_state("conv")["manifest"]) == {"b"}
    assert runtime.get_conversation_graph_cache("conv") == reads[-1]


@pytest.mark.parametrize("cache", ["missing", "wrong_conversation", "empty_graph"])
def test_runtime_cache_read_rejects_unusable_snapshot(graph_store, monkeypatch, cache):
    service = graph_store.service()
    runtime = _runtime(graph_store, service, "owner", monkeypatch)
    if cache != "missing":
        build(graph_store, service, ["a"])
        state = service._load_cached_state("conv")
        if cache == "wrong_conversation":
            state["conversation_id"] = "other"
        else:
            state["graph"] = None
        service._save_cached_state("conv", state)
    assert runtime.get_conversation_graph_cache("conv") is None


def test_runtime_cache_read_does_not_disclose_private_conversation(
    graph_store, monkeypatch
):
    service = graph_store.service()
    build(graph_store, service, ["a"])
    runtime = _runtime(graph_store, service, "attacker", monkeypatch)
    with pytest.raises(PermissionError):
        runtime.get_conversation_graph_cache("conv")


def test_runtime_cache_read_rejects_deleted_conversation(graph_store, monkeypatch):
    service = graph_store.service()
    build(graph_store, service, ["a"])
    runtime = _runtime(graph_store, service, "owner", monkeypatch)
    with Session(graph_store.engine) as session:
        session.delete(session.get(Conversation, "conv"))
        session.commit()
    with pytest.raises(PermissionError):
        runtime.get_conversation_graph_cache("conv")
