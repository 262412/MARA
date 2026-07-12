from types import SimpleNamespace

from ktem.db.models import Conversation, engine
from ktem.docqa._runtime_notebook import NOTEBOOK_KEY
from ktem.pages.chat.studio_note_actions import convert_note_to_source_update
from sqlmodel import Session, select


def test_convert_note_to_source_update_indexes_note_and_refreshes_panel(
    monkeypatch,
    tmp_path,
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
    index_result = SimpleNamespace(
        successes=[{"source_id": "file-note-1"}],
        failures=[],
        as_dict=lambda: {"successes": [{"source_id": "file-note-1"}], "failures": []},
    )
    runtime = SimpleNamespace(
        _resolve_user_id=lambda: "user-1",
        index_paths=lambda _paths, reindex=False, user_id=None: index_result,
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
    finally:
        with Session(engine) as session:
            cleanup_row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if cleanup_row is not None:
                session.delete(cleanup_row)
                session.commit()
