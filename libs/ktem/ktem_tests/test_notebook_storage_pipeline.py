"""Real materialization, SQL, Lance, Chroma and export boundaries; no model calls."""

from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import pytest
from ktem.db.models import Conversation
from ktem.docqa import _runtime_notebook as notebook
from ktem.docqa.artifact_exports import export_artifact_to_path
from ktem.pages.chat.studio_note_actions import convert_note_to_source_update
from sqlmodel import Session

support = import_module("libs.ktem.ktem_tests.indexing_backend_test_support")
backend = support.backend


@pytest.fixture
def note_store(backend, monkeypatch, tmp_path):
    Conversation.__table__.create(backend.engine)
    monkeypatch.setattr(notebook, "engine", backend.engine)
    monkeypatch.setattr(
        notebook._materialization,
        "default_note_sources_dir",
        lambda: tmp_path / "notes",
    )
    with Session(backend.engine) as session:
        session.add(Conversation(id="owned", user="alice"))
        session.commit()
    notebook.add_note_to_conversation(
        "owned",
        user_id="alice",
        title="Evidence",
        text="Deterministic evidence.",
        note_id="note",
    )
    return backend


@pytest.mark.parametrize(
    "failure", [None, "materialize", "index", "backfill", "deleted"]
)
def test_note_materialization_index_and_backfill_record_actual_stage(
    note_store, monkeypatch, tmp_path, failure
):
    indexed = []

    def index_paths(paths, **kwargs):
        assert Path(paths[0]).is_file()
        if failure == "index":
            return SimpleNamespace(failures=["controlled indexing failure"])
        pipeline = note_store.pipeline()
        _events, result = support.drain(pipeline.stream(Path(paths[0]), reindex=False))
        indexed.append(result[0])
        if failure == "deleted":
            with Session(note_store.engine) as session:
                session.delete(session.get(Conversation, "owned"))
                session.commit()
        return SimpleNamespace(failures=[], successes=[{"source_id": result[0]}])

    def fail(*args, **kwargs):
        raise OSError("controlled stage failure")

    if failure == "materialize":
        monkeypatch.setattr(notebook, "materialize_note_source", fail)
    elif failure == "backfill":

        class FailedCommit(Session):
            def commit(self):
                raise OSError("controlled stage failure")

        monkeypatch.setattr(notebook, "Session", FailedCommit)

    page = SimpleNamespace(
        docqa=SimpleNamespace(
            _resolve_user_id=lambda: "alice", index_paths=index_paths
        ),
        _resolve_persist_user_id=lambda user, request: user,
    )
    if failure in {"materialize", "backfill", "deleted"}:
        with pytest.raises((OSError, notebook.NotebookAccessError)):
            convert_note_to_source_update(page, "owned", "note")
    else:
        convert_note_to_source_update(page, "owned", "note")

    source_path = tmp_path / "notes" / "owned" / "mara-note-note.md"
    assert source_path.exists() == (failure != "materialize")
    sources = support.rows(note_store, "Source")
    assert len(sources) == (1 if failure in {None, "backfill", "deleted"} else 0)
    if sources:
        assert sources[0].id == indexed[0]
        relations = support.rows(note_store, "Index")
        document_ids = [
            row.target_id for row in relations if row.relation_type == "document"
        ]
        vector_ids = [
            row.target_id for row in relations if row.relation_type == "vector"
        ]
        assert document_ids and vector_ids
        assert note_store.documents.get(document_ids)
        assert set(note_store.vectors._collection.get(ids=vector_ids)["ids"]) == set(
            vector_ids
        )
    if failure == "deleted":
        with Session(note_store.engine) as session:
            assert session.get(Conversation, "owned") is None
    else:
        note = notebook.get_notebook("owned", user_id="alice")["notes"][0]
        assert note.get("indexed_source_ids", []) == (
            indexed if failure is None else []
        )


@pytest.mark.parametrize("registration_fails", [False, True])
def test_export_registration_reload_and_record_deletion_keep_disk_file(
    note_store, monkeypatch, tmp_path, registration_fails
):
    record = notebook.save_artifact_to_conversation(
        "owned",
        user_id="alice",
        artifact_type="study_guide",
        artifact_id="artifact",
        payload={"overview": "Evidence on disk"},
    )
    path = export_artifact_to_path(
        record, export_format="md", output_path=tmp_path / "exports" / "artifact.md"
    )
    content = path.read_bytes()
    if registration_fails:

        class FailedCommit(Session):
            def commit(self):
                raise OSError("registration failed")

        with monkeypatch.context() as patch:
            patch.setattr(notebook, "Session", FailedCommit)
            with pytest.raises(OSError, match="registration failed"):
                notebook.record_artifact_export_to_conversation(
                    "owned",
                    "artifact",
                    user_id="alice",
                    export_format="md",
                    path=str(path),
                )
    else:
        notebook.record_artifact_export_to_conversation(
            "owned", "artifact", user_id="alice", export_format="md", path=str(path)
        )
    loaded = notebook.get_notebook("owned", user_id="alice")["artifacts"][0]
    assert len(loaded["exports"]) == (0 if registration_fails else 1)
    if not registration_fails:
        assert loaded["exports"][0]["path"] == str(path)
    notebook.delete_artifact_from_conversation("owned", "artifact", user_id="alice")
    assert notebook.get_notebook("owned", user_id="alice")["artifacts"] == []
    assert path.read_bytes() == content
