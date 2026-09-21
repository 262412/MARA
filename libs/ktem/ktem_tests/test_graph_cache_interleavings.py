"""Cache validity is checked on disk as well as at the displayed-result boundary."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest
from ktem.db.models import Conversation
from ktem.docqa import knowledge_graph as runtime_graph
from ktem.pages.chat import knowledge_graph_service as web_graph
from ktem.preview.errors import PreviewAccessError
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base
from sqlmodel import Session, create_engine


@pytest.fixture(params=[runtime_graph, web_graph], ids=["runtime", "web"])
def graph_store(request, monkeypatch, tmp_path):
    module = request.param
    engine = create_engine(f"sqlite:///{tmp_path / 'graph.db'}")
    base = declarative_base()

    class Source(base):  # type: ignore[valid-type,misc]
        __tablename__ = "owned_graph_source"
        id = Column(String, primary_key=True)
        name = Column(String)
        path = Column(String)
        size = Column(Integer, default=1)
        date_created = Column(DateTime)
        user = Column(String)

    class Index(base):  # type: ignore[valid-type,misc]
        __tablename__ = "owned_graph_index"
        id = Column(Integer, primary_key=True)
        source_id = Column(String)
        target_id = Column(String)
        relation_type = Column(String)

    base.metadata.create_all(engine)
    Conversation.__table__.create(engine)
    with Session(engine) as session:
        session.add(Conversation(id="conv", user="owner"))
        session.add(Conversation(id="other", user="owner"))
        for key in ("a", "b"):
            session.add(Source(id=key, name=key, path=key, user="owner"))
        session.commit()
    index = SimpleNamespace(
        id=1,
        config={"private": True},
        _resources={
            "Source": Source,
            "Index": Index,
            "FileStoragePath": tmp_path,
            "DocStore": SimpleNamespace(get=lambda ids: []),
        },
    )
    app = SimpleNamespace(
        f_user_management=True, index_manager=SimpleNamespace(indices=[index])
    )
    monkeypatch.setattr(module, "engine", engine)
    monkeypatch.setattr(module.flowsettings, "KH_APP_DATA_DIR", tmp_path)

    def service():
        return module.GlobalKnowledgeGraphService(app, index)

    yield SimpleNamespace(
        engine=engine, Source=Source, Index=Index, service=service, module=module
    )
    engine.dispose()


def build(store, service, ids, cid="conv"):
    if store.module is runtime_graph:
        return service.build_graph(cid, ids, user_id="owner")
    return service.get_graph_view(cid, ids, force_rebuild=True, user_id="owner")


def intercept_build(store, service, monkeypatch, callback):
    name = (
        "_build_nodes_and_edges"
        if store.module is runtime_graph
        else "_build_conversation_graph"
    )
    original = getattr(service, name)

    def controlled(*args, **kwargs):
        result = original(*args, **kwargs)
        callback()
        return result

    monkeypatch.setattr(service, name, controlled)


@pytest.mark.parametrize("removed", ["source", "conversation"])
def test_deleted_input_rejects_late_disk_publication(graph_store, monkeypatch, removed):
    store = graph_store
    service = store.service()

    def delete():
        with Session(store.engine) as session:
            table, key = (
                (store.Source, "a") if removed == "source" else (Conversation, "conv")
            )
            session.delete(session.get(table, key))
            session.commit()

    intercept_build(store, service, monkeypatch, delete)
    with pytest.raises((RuntimeError, PermissionError)):
        build(store, service, ["a"])
    assert not service._get_storage_path("conv").exists()


def test_old_build_cannot_replace_newer_a_b_a_request(graph_store, monkeypatch):
    store = graph_store
    first, latest = store.service(), store.service()
    started, release = Event(), Event()

    def pause():
        started.set()
        assert release.wait(15)

    intercept_build(store, first, monkeypatch, pause)
    with ThreadPoolExecutor(1) as pool:
        old = pool.submit(build, store, first, ["a"])
        try:
            assert started.wait(10)
            build(store, latest, ["b"])
            build(store, latest, ["a"])
            completed = latest._get_storage_path("conv").read_bytes()
        finally:
            release.set()
        with pytest.raises(RuntimeError):
            old.result(timeout=10)
    assert latest._get_storage_path("conv").read_bytes() == completed


def test_draft_never_publishes_a_shared_disk_snapshot(graph_store):
    service = graph_store.service()
    result = build(graph_store, service, ["a"], cid="")
    assert result["graph"] is not None
    assert not service._get_storage_path("draft").exists()


def test_cached_graph_does_not_authorize_another_conversation(graph_store):
    store = graph_store
    service = store.service()
    with Session(store.engine) as session:
        row = session.get(Conversation, "conv")
        assert row is not None
        row.user = "someone-else"
        session.add(row)
        session.commit()
    with pytest.raises(PermissionError):
        build(store, service, ["a"])


@pytest.mark.parametrize("change", ["reindex", "source_owner", "public_scope"])
def test_changed_input_rejects_late_disk_publication(graph_store, monkeypatch, change):
    store, service = graph_store, graph_store.service()

    def modify():
        with Session(store.engine) as session:
            if change == "reindex":
                session.add(
                    store.Index(
                        source_id="a",
                        target_id="new-generation",
                        relation_type="document",
                    )
                )
            elif change == "source_owner":
                row = session.get(store.Source, "a")
                assert row is not None
                row.user = "other-owner"
                session.add(row)
            else:
                row = session.get(Conversation, "conv")
                assert row is not None
                row.data_source = {"graph_source_ids": ["b"]}
                session.add(row)
            session.commit()

    intercept_build(store, service, monkeypatch, modify)
    with pytest.raises(RuntimeError):
        build(store, service, ["a"])
    assert not service._get_storage_path("conv").exists()


def test_same_source_in_two_conversations_has_independent_disk_state(graph_store):
    store = graph_store
    service = store.service()
    build(store, service, ["a"], "conv")
    first = service._get_storage_path("conv").read_bytes()
    build(store, service, ["a"], "other")
    assert service._get_storage_path("conv").read_bytes() == first
    assert service._load_cached_state("other")["conversation_id"] == "other"


def test_two_owners_cannot_hit_each_others_graph(graph_store):
    store, service = graph_store, graph_store.service()
    build(store, service, ["a"], "conv")
    with Session(store.engine) as session:
        other = session.get(Conversation, "other")
        assert other is not None
        other.user = "bob"
        session.add(other)
        source = session.get(store.Source, "b")
        assert source is not None
        source.user = "bob"
        session.add(source)
        session.commit()
    if store.module is runtime_graph:
        service.build_graph("other", ["b"], user_id="bob")
        with pytest.raises(PreviewAccessError):
            service.build_graph("other", ["a"], user_id="bob")
    else:
        service.get_graph_view("other", ["b"], force_rebuild=True, user_id="bob")
        with pytest.raises(PreviewAccessError):
            service.get_graph_view("other", ["a"], user_id="bob")
    assert service._load_cached_state("conv")["conversation_id"] == "conv"
