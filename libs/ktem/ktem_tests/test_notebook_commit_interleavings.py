"""Independent Session interleavings at the real read/modify/commit boundary."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event, current_thread
from types import ModuleType, SimpleNamespace

import pytest
from filelock import Timeout
from ktem.db.models import Conversation
from ktem.docqa import _runtime_notebook as notebook
from ktem.docqa import _runtime_sessions as sessions
from ktem.docqa._runtime_session_mutations import RuntimeSessionMutationService
from ktem.docqa._runtime_session_service import RuntimeSessionService
from ktem.index.file.source_writes import _SourceFileLock
from sqlalchemy import event
from sqlmodel import Session, create_engine


@pytest.fixture
def store(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'conversations.db'}")
    Conversation.__table__.create(engine)
    monkeypatch.setattr(notebook, "engine", engine)
    with Session(engine) as session:
        row = Conversation(user="owner", data_source={"origin": "web"})
        session.add(row)
        session.commit()
        session.refresh(row)
        conversation_id = row.id
    service = RuntimeSessionService(
        app=SimpleNamespace(index_manager=SimpleNamespace(indices=[])),
        file_index=None,
        engine=engine,
        resolve_user_id=lambda user: user,
    )
    mutations = RuntimeSessionMutationService(
        engine=engine, resolve_user_id=lambda user: user
    )
    yield engine, conversation_id, service, mutations
    engine.dispose()


def _add(cid, note_id):
    return notebook.add_note_to_conversation(
        cid, user_id="owner", title=note_id, text=note_id, note_id=note_id
    )


def _chat(service, cid):
    return service.persist_conversation_state(
        cid,
        "owner",
        "evidence",
        None,
        [],
        [],
        [("q", "a")],
        {"app": {"regen": False}},
        [],
        origin="web",
    )


def _interleave(engine, monkeypatch, target, name, first, second):
    first_read = Event()
    release = Event()
    second_boundary = Event()
    lease_waiting = Event()
    original = getattr(target, name)
    acquire = _SourceFileLock.acquire

    def hold(*args, **kwargs):
        if current_thread().name.startswith("first"):
            first_read.set()
            assert release.wait(10), "test producer was not released"
        return original(*args, **kwargs)

    def read_observed(_conn, _cursor, sql, _params, _context, _many):
        if current_thread().name.startswith("second") and sql.startswith("SELECT"):
            second_boundary.set()

    def acquisition_observed(lock, *args, **kwargs):
        if current_thread().name.startswith("second"):
            try:
                return acquire(lock, timeout=0)
            except Timeout:
                lease_waiting.set()
                second_boundary.set()
        return acquire(lock, *args, **kwargs)

    monkeypatch.setattr(target, name, hold)
    monkeypatch.setattr(_SourceFileLock, "acquire", acquisition_observed)
    event.listen(engine, "after_cursor_execute", read_observed)
    with ThreadPoolExecutor(1, thread_name_prefix="first") as a_pool:
        with ThreadPoolExecutor(1, thread_name_prefix="second") as b_pool:
            a = a_pool.submit(first)
            try:
                assert first_read.wait(10)
                b = b_pool.submit(second)
                assert second_boundary.wait(10)
                # If there is no lease the second writer commits while A still
                # holds its detached JSON. With a lease B cannot start its read.
                if not lease_waiting.is_set():
                    b.result(timeout=10)
            finally:
                release.set()
            a.result(timeout=10)
            b.result(timeout=10)
    event.remove(engine, "after_cursor_execute", read_observed)


def test_two_notes_keep_both_independent_session_updates(store, monkeypatch):
    engine, cid, _service, _mutations = store
    _interleave(
        engine,
        monkeypatch,
        notebook,
        "add_note",
        lambda: _add(cid, "first"),
        lambda: _add(cid, "second"),
    )
    notes = notebook.get_notebook(cid, user_id="owner")["notes"]
    assert {note["note_id"] for note in notes} == {"first", "second"}


@pytest.mark.parametrize("chat_first", [False, True])
def test_notebook_and_chat_preserve_both_domains(store, monkeypatch, chat_first):
    engine, cid, service, _mutations = store
    first, second = lambda: _add(cid, "note"), lambda: _chat(service, cid)
    target: ModuleType = notebook
    name = "add_note"
    if chat_first:
        first, second = second, first
        target, name = sessions, "build_conversation_data_source"
    _interleave(engine, monkeypatch, target, name, first, second)
    loaded = service.load_session(cid, user_id="owner")
    assert loaded.data_source["messages"] == [["q", "a"]]
    assert notebook.list_notes(loaded.data_source)[0]["note_id"] == "note"


def test_export_registration_cannot_resurrect_deleted_artifact(store, monkeypatch):
    engine, cid, _service, _mutations = store
    notebook.save_artifact_to_conversation(
        cid,
        user_id="owner",
        artifact_type="study_guide",
        artifact_id="artifact",
        payload={"text": "owned"},
    )
    _interleave(
        engine,
        monkeypatch,
        notebook,
        "record_artifact_export",
        lambda: notebook.record_artifact_export_to_conversation(
            cid, "artifact", user_id="owner", export_format="md", path="owned.md"
        ),
        lambda: notebook.delete_artifact_from_conversation(
            cid, "artifact", user_id="owner"
        ),
    )
    assert notebook.get_notebook(cid, user_id="owner")["artifacts"] == []


def test_note_index_backfill_and_source_selection_preserve_current_fields(
    store, monkeypatch
):
    engine, cid, _service, _mutations = store
    _add(cid, "note")
    _interleave(
        engine,
        monkeypatch,
        notebook,
        "record_note_indexed_source",
        lambda: notebook.record_note_indexed_source_to_conversation(
            cid, "note", user_id="owner", source_ids=["indexed"], source_path="owned.md"
        ),
        lambda: notebook.select_conversation_sources(
            cid, ["selected"], user_id="owner"
        ),
    )
    loaded = notebook.get_notebook(cid, user_id="owner")
    assert loaded["selected_source_ids"] == ["selected"]
    assert loaded["notes"][0]["indexed_source_ids"] == ["indexed"]
