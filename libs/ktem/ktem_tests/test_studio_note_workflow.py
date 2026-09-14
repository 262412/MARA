from types import SimpleNamespace

import pytest
from ktem.db.models import Conversation, engine
from ktem.docqa._runtime_models import DocQAIndexResult
from ktem.docqa._runtime_notebook import NOTEBOOK_KEY
from ktem.pages.chat.studio_note_actions import convert_note_to_source_update
from sqlmodel import Session, select


@pytest.mark.parametrize("reported_id", [True, False])
def test_convert_note_to_source_update_indexes_note_and_refreshes_panel(
    monkeypatch,
    tmp_path,
    reported_id,
):
    from theflow.settings import settings as flowsettings

    monkeypatch.setattr(flowsettings, "KH_APP_DATA_DIR", tmp_path, raising=False)
    conversation = Conversation(user="user-1")
    conversation.data_source = {
        NOTEBOOK_KEY: {
            "selected_source_ids": [],
            "notes": [
                {
                    "note_id": "note-1",
                    "title": "Manual insight",
                    "text": "Index this note.",
                }
            ],
            "artifacts": [],
        }
    }
    success = (
        {"source_id": "file-note-1"}
        if reported_id
        else {"status": "success", "file_name": "mara-note-note-1.md"}
    )
    index_result = DocQAIndexResult(
        successes=[success],
        failures=[],
        debug_messages=[],
    )
    resolutions = []

    def resolve_file_refs(refs, user_id):
        resolutions.append((refs, user_id))
        return [SimpleNamespace(file_id="file-note-1")]

    runtime = SimpleNamespace(
        _resolve_user_id=lambda: "user-1",
        index_paths=lambda _paths, reindex=False, user_id=None: index_result,
        resolve_file_refs=resolve_file_refs,
    )
    page = SimpleNamespace(
        docqa=runtime,
        _resolve_persist_user_id=lambda user_id, _request: user_id,
    )
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id

    try:
        html = convert_note_to_source_update(page, conversation_id, "note-1")

        assert "1 selected" in html
        with Session(engine) as session:
            row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one()
        notebook = row.data_source[NOTEBOOK_KEY]
        assert notebook["selected_source_ids"] == ["file-note-1"]
        assert notebook["notes"][0]["indexed_source_ids"] == ["file-note-1"]
        assert notebook["notes"][0]["indexed_source_path"].endswith(
            "mara-note-note-1.md"
        )
        assert resolutions == (
            [] if reported_id else [(["mara-note-note-1.md"], "user-1")]
        )
    finally:
        with Session(engine) as session:
            cleanup_row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if cleanup_row is not None:
                session.delete(cleanup_row)
                session.commit()
