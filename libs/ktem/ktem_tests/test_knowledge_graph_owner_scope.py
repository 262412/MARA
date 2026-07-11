from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from gradio.helpers import special_args
from ktem.docqa.knowledge_graph import (
    GlobalKnowledgeGraphService as DocQAKnowledgeGraphService,
)
from ktem.pages.chat.knowledge_graph_service import (
    GlobalKnowledgeGraphService as WebKnowledgeGraphService,
)
from ktem.pages.chat.studio_artifact_controls import (
    _bind_page_callback,
    generate_studio_artifact_panel_update,
)
from ktem.pages.chat.studio_artifact_mindmap import _build_graph_view
from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base


class _DocStoreSpy:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def get(self, document_ids):
        self.calls.append(list(document_ids))
        raise AssertionError("docstore read happened before source authorization")


@pytest.fixture
def managed_graph_app(monkeypatch, tmp_path):
    base = declarative_base()

    class Source(base):  # type: ignore[valid-type,misc]
        __tablename__ = "task_12c2_graph_source"
        id = Column(String, primary_key=True)
        name = Column(String)
        path = Column(String)
        size = Column(Integer, default=0)
        date_created = Column(DateTime)
        user = Column(String)

    class Index(base):  # type: ignore[valid-type,misc]
        __tablename__ = "task_12c2_graph_index"
        id = Column(Integer, primary_key=True, autoincrement=True)
        source_id = Column(String)
        target_id = Column(String)
        relation_type = Column(String)

    db_engine = create_engine("sqlite://")
    base.metadata.create_all(db_engine)
    with Session(db_engine) as session:
        session.add_all(
            [
                Source(
                    id="attacker-file",
                    name="Own.pdf",
                    path="own-hash",
                    size=10,
                    user="attacker",
                ),
                Source(
                    id="victim-file",
                    name="Secret.pdf",
                    path="victim-hash",
                    size=20,
                    user="victim",
                ),
                Index(
                    source_id="victim-file",
                    target_id="victim-doc",
                    relation_type="document",
                ),
            ]
        )
        session.commit()

    docstore = _DocStoreSpy()
    index = SimpleNamespace(
        id=1,
        config={"private": False},
        _resources={
            "Source": Source,
            "Index": Index,
            "DocStore": docstore,
            "FileStoragePath": tmp_path / "storage",
        },
    )
    app = SimpleNamespace(
        f_user_management=True,
        index_manager=SimpleNamespace(indices=[index]),
    )
    monkeypatch.setattr("ktem.pages.chat.knowledge_graph_service.engine", db_engine)
    monkeypatch.setattr("ktem.docqa.knowledge_graph.engine", db_engine)
    monkeypatch.setattr(
        "ktem.pages.chat.knowledge_graph_service.flowsettings.KH_APP_DATA_DIR",
        tmp_path / "web-app-data",
        raising=False,
    )
    monkeypatch.setattr(
        "ktem.docqa.knowledge_graph.flowsettings.KH_APP_DATA_DIR",
        tmp_path / "docqa-app-data",
        raising=False,
    )
    return app, index, docstore


def _assert_access_error(caught: pytest.ExceptionInfo[Exception]) -> None:
    assert type(caught.value).__name__ == "PreviewAccessError"
    assert "source_unavailable" in str(caught.value)


def test_web_knowledge_graph_rejects_victim_before_docstore_read(
    managed_graph_app,
):
    app, index, docstore = managed_graph_app
    service = WebKnowledgeGraphService(app, index)

    with pytest.raises(Exception) as caught:
        service.get_graph_view(
            "conversation-1",
            ["attacker-file", "victim-file"],
            force_rebuild=True,
            user_id="attacker",
        )

    _assert_access_error(caught)
    assert docstore.calls == []


def test_docqa_knowledge_graph_rejects_victim_before_docstore_read(
    monkeypatch,
    managed_graph_app,
):
    app, index, docstore = managed_graph_app
    service = DocQAKnowledgeGraphService(app, index)
    cache_calls: list[str] = []

    def reject_cache_read(conversation_id):
        cache_calls.append(conversation_id)
        raise AssertionError("cache read happened before source authorization")

    monkeypatch.setattr(service, "_load_cached_state", reject_cache_read)

    with pytest.raises(Exception) as caught:
        service.build_graph(
            "conversation-1",
            ["attacker-file", "victim-file"],
            user_id="attacker",
        )

    _assert_access_error(caught)
    assert cache_calls == []
    assert docstore.calls == []


def test_docqa_knowledge_graph_resolves_authorized_sources_once(
    monkeypatch,
    managed_graph_app,
):
    app, index, _docstore = managed_graph_app
    service = DocQAKnowledgeGraphService(app, index)
    resolve_calls: list[list[str]] = []
    resolve_sources = service._preview.resolve_sources

    def resolve_once(file_ids, **kwargs):
        resolve_calls.append(list(file_ids))
        return resolve_sources(file_ids, **kwargs)

    monkeypatch.setattr(service._preview, "resolve_sources", resolve_once)

    state = service.build_graph(
        "conversation-1",
        ["attacker-file"],
        user_id="attacker",
    )

    assert resolve_calls == [["attacker-file"]]
    assert set(state) == {"conversation_id", "manifest", "graph"}
    assert list(state["manifest"]) == ["attacker-file"]


def test_docqa_knowledge_graph_empty_scope_resolves_once_before_cache(
    monkeypatch,
    managed_graph_app,
):
    app, index, _docstore = managed_graph_app
    service = DocQAKnowledgeGraphService(app, index)
    events: list[str] = []
    cache_loaded = False
    load_sources = service._load_sources
    load_cached_state = service._load_cached_state

    def trace_sources(*args, **kwargs):
        events.append("sources-after-cache" if cache_loaded else "sources-before-cache")
        return load_sources(*args, **kwargs)

    def trace_cache(*args, **kwargs):
        nonlocal cache_loaded
        cache_loaded = True
        events.append("cache")
        return load_cached_state(*args, **kwargs)

    monkeypatch.setattr(service, "_load_sources", trace_sources)
    monkeypatch.setattr(service, "_load_cached_state", trace_cache)

    state = service.build_graph("conversation-empty", [], user_id="attacker")

    assert events == ["sources-before-cache", "cache"]
    assert state == {
        "conversation_id": "conversation-empty",
        "manifest": {},
        "graph": {"nodes": [], "edges": [], "clusters": {}},
    }


class _StudioGraphBoundary:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get_graph_view(self, **kwargs):
        self.calls.append(dict(kwargs))
        raise PermissionError("source_unavailable")


def test_studio_mindmap_passes_resolved_user_to_strict_graph_boundary():
    graph = _StudioGraphBoundary()
    page = SimpleNamespace(knowledge_graph=graph)
    values = {"active_file_id": "victim-file", "user_id": "attacker"}

    with pytest.raises(PermissionError, match="source_unavailable"):
        _build_graph_view(
            page,
            values,
            "conversation-1",
            ["victim-file"],
        )

    assert graph.calls == [
        {
            "conversation_id": "conversation-1",
            "graph_source_ids": ["victim-file"],
            "focus_file_id": "victim-file",
            "force_rebuild": True,
            "user_id": "attacker",
        }
    ]


def test_studio_root_receives_request_before_variable_selector_tail():
    callback = _bind_page_callback(generate_studio_artifact_panel_update, object())
    component_inputs = [
        "mindmap",
        "Build a map.",
        "multi-document",
        "html",
        "",
        0,
        "conversation-1",
        [],
        {},
        "mara",
        "model",
        "default",
        "default",
        "English",
        {},
        None,
        "victim-state-user",
        "victim-file",
        "Victim.pdf",
        1,
        "",
        "{}",
        "llm",
        "auto",
        "light",
        "",
        "",
        "selector-mode",
        ["victim-file"],
    ]
    request = cast(Any, SimpleNamespace(username="attacker"))

    injected, _, _ = special_args(
        callback,
        inputs=list(component_inputs),
        request=request,
    )

    assert injected == [*component_inputs[:27], request, *component_inputs[27:]]
