from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import ktem.index.file._scoped_page as scoped_page_module
import ktem.index.file._selector_ui as selector_ui_module
import ktem.index.file.ui as file_ui_module
import pytest
from gradio.helpers import special_args
from ktem.index.file._group_service import FileGroupService, GroupServiceError
from ktem.index.file._selection_service import FileSelectionService
from ktem.index.file.ui import FileIndexPage, FileSelector
from sqlalchemy import JSON, Column, DateTime, String, create_engine
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Session, declarative_base


@pytest.fixture
def private_file_database():
    base = declarative_base()

    class Source(base):  # type: ignore[valid-type,misc]
        __tablename__ = "scoped_source"
        id = Column(String, primary_key=True, default=lambda: uuid4().hex)
        name = Column(String)
        user = Column(String)

    class Index(base):  # type: ignore[valid-type,misc]
        __tablename__ = "scoped_index"
        id = Column(String, primary_key=True, default=lambda: uuid4().hex)
        source_id = Column(String)
        target_id = Column(String)
        relation_type = Column(String)

    class FileGroup(base):  # type: ignore[valid-type,misc]
        __tablename__ = "scoped_file_group"
        id = Column(String, primary_key=True, default=lambda: uuid4().hex)
        name = Column(String)
        user = Column(String)
        data = Column(MutableDict.as_mutable(JSON), default={"files": []})
        date_created = Column(DateTime, default=datetime.now)

    db_engine = create_engine("sqlite://")
    base.metadata.create_all(db_engine)
    index = SimpleNamespace(
        config={"private": True},
        _resources={"Source": Source, "Index": Index, "FileGroup": FileGroup},
        _docstore=SimpleNamespace(
            get=lambda ids: [
                SimpleNamespace(
                    text=f"secret:{item}",
                    metadata={"type": "text", "page_label": "1"},
                )
                for item in ids
            ]
        ),
    )
    return index, Source, Index, FileGroup, db_engine


def test_private_group_read_update_and_delete_require_owner(private_file_database):
    index, _source, _index_table, group_table, db_engine = private_file_database
    service = FileGroupService(index=index, engine=db_engine)
    group_id = service.save_group(None, "Victim", ["secret-file"], "victim")

    with pytest.raises(GroupServiceError, match="No group found"):
        service.selected_file_ids(group_id, "attacker")
    with pytest.raises(GroupServiceError, match="No group found"):
        service.save_group(group_id, "Stolen", ["attacker-file"], "attacker")
    with pytest.raises(GroupServiceError, match="No group found"):
        service.delete_group(group_id, "attacker")

    with Session(db_engine) as session:
        row = session.query(group_table).filter_by(id=group_id).one()
        assert row.name == "Victim"
        assert row.data == {"files": ["secret-file"]}

    assert service.selected_file_ids(group_id, "victim") == ['["secret-file"]']
    assert service.delete_group(group_id, "victim") == "Victim"


def test_public_index_groups_remain_owner_scoped(private_file_database):
    index, _source, _index_table, group_table, db_engine = private_file_database
    index.config = {"private": False}
    service = FileGroupService(index=index, engine=db_engine)
    group_id = service.save_group(None, "Victim", ["victim-file"], "victim")

    rows, _frame = service.list_groups("attacker", [])
    assert rows == []
    with pytest.raises(GroupServiceError, match="No group found"):
        service.selected_file_ids(group_id, "attacker")
    with pytest.raises(GroupServiceError, match="No group found"):
        service.save_group(group_id, "Stolen", ["attacker-file"], "attacker")
    with pytest.raises(GroupServiceError, match="No group found"):
        service.delete_group(group_id, "attacker")

    with Session(db_engine) as session:
        row = session.query(group_table).filter_by(id=group_id).one()
        assert row.name == "Victim"
        assert row.user == "victim"
        assert row.data == {"files": ["victim-file"]}


def test_private_chunk_rendering_and_source_lookup_require_owner(
    private_file_database,
):
    index, source_table, index_table, _group_table, db_engine = private_file_database
    with Session(db_engine) as session:
        session.add(source_table(id="victim-file", name="secret.pdf", user="victim"))
        session.add(
            index_table(
                source_id="victim-file",
                target_id="victim-doc",
                relation_type="document",
            )
        )
        session.commit()

    service = FileSelectionService(
        index=index,
        engine=db_engine,
        sort_key=lambda document: document.metadata["page_label"],
    )

    with pytest.raises(PermissionError, match="authenticated user scope"):
        service.render_chunks("victim-file", "attacker")
    with pytest.raises(PermissionError, match="authenticated user scope"):
        service.source_name("victim-file", "attacker")

    assert "secret:victim-doc" in service.render_chunks("victim-file", "victim")
    assert service.source_name("victim-file", "victim") == "secret.pdf"


class _SelectionSpy:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def render_chunks(self, file_id, user_id):
        self.calls.append((file_id, user_id))
        return "safe chunks"


def test_file_page_selection_uses_server_identity(monkeypatch):
    page = cast(Any, FileIndexPage.__new__(FileIndexPage))
    service = _SelectionSpy()
    page._get_file_selection_service = lambda: service
    monkeypatch.setattr(
        scoped_page_module,
        "resolve_file_index_user_id",
        lambda _browser_user, _request: "server-user",
        raising=False,
    )

    outputs = page.file_selected(
        "victim-file",
        "browser-user",
        request=SimpleNamespace(username="alice"),
    )

    assert service.calls == [("victim-file", "server-user")]
    assert outputs[0]["value"] == "safe chunks"


class _IndexingSpy:
    def __init__(self):
        self.user_ids: list[str] = []

    def index_files_with_default_loaders(
        self,
        _files,
        *,
        reindex,
        settings,
        user_id,
    ):
        self.user_ids.append(user_id)
        return ["new-file"]


def test_file_page_indexing_uses_server_identity(monkeypatch):
    page = cast(Any, FileIndexPage.__new__(FileIndexPage))
    service = _IndexingSpy()
    page._get_indexing_service = lambda **_kwargs: service
    monkeypatch.setattr(
        file_ui_module,
        "resolve_file_index_user_id",
        lambda _browser_user, _request: "server-user",
        raising=False,
    )

    result = page.index_fn_file_with_default_loaders(
        ["report.pdf"],
        False,
        {},
        "browser-user",
        request=SimpleNamespace(username="alice"),
    )

    assert result == ["new-file"]
    assert service.user_ids == ["server-user"]


def test_gradio_injects_file_scope_request_after_component_inputs():
    page = cast(Any, FileIndexPage.__new__(FileIndexPage))
    request = SimpleNamespace(username="alice")

    selected_inputs, _, _ = special_args(
        page.file_selected,
        inputs=["file-1", "browser-user"],
        request=cast(Any, request),
    )
    indexing_inputs, _, _ = special_args(
        page.index_fn_file_with_default_loaders,
        inputs=[["report.pdf"], False, {}, "browser-user"],
        request=cast(Any, request),
    )

    assert selected_inputs == ["file-1", "browser-user", request]
    assert indexing_inputs == [
        ["report.pdf"],
        False,
        {},
        "browser-user",
        request,
    ]


def test_file_selector_load_uses_server_identity(
    private_file_database,
    monkeypatch,
):
    index, source_table, _index_table, _group_table, db_engine = private_file_database
    with Session(db_engine) as session:
        session.add(source_table(id="server-file", name="own.pdf", user="server-user"))
        session.add(source_table(id="victim-file", name="secret.pdf", user="victim"))
        session.commit()

    selector = cast(Any, FileSelector.__new__(FileSelector))
    selector._index = index
    monkeypatch.setattr(selector_ui_module, "engine", db_engine)
    monkeypatch.setattr(
        selector_ui_module,
        "resolve_file_index_user_id",
        lambda _browser_user, _request: "server-user",
    )

    update, options = selector.load_files(
        [],
        "victim",
        request=SimpleNamespace(username="alice"),
    )

    assert update["choices"] == [("own.pdf", "server-file")]
    assert options == [("own.pdf", "server-file")]
