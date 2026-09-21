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
