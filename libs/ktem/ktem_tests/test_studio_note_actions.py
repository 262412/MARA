from ktem.db.models import Conversation, engine
from ktem.docqa._runtime_notebook import NOTEBOOK_KEY
from ktem.pages.chat.studio_note_actions import (
    save_latest_answer_note_update,
    save_latest_artifact_note_update,
    save_manual_note_update,
)
from sqlmodel import Session, select


def _cleanup_conversation(conversation_id: str) -> None:
    with Session(engine) as session:
        cleanup_row = session.exec(
            select(Conversation).where(Conversation.id == conversation_id)
        ).one_or_none()
        if cleanup_row is not None:
            session.delete(cleanup_row)
            session.commit()


def test_save_latest_artifact_note_update_persists_note_and_refreshes_panel():
    conversation = Conversation(user="user-1")
    conversation.data_source = {
        NOTEBOOK_KEY: {
            "selected_source_ids": ["file-1"],
            "notes": [],
            "artifacts": [
                {
                    "artifact_id": "artifact-1",
                    "type": "study_guide",
                    "title": "Older guide",
                    "payload": {"overview": "Older."},
                },
                {
                    "artifact_id": "artifact-2",
                    "type": "briefing_doc",
                    "title": "Launch briefing",
                    "prompt": "Create an executive briefing.",
                    "payload": {
                        "sections": [
                            {
                                "title": "Finding",
                                "summary": "Source-grounded launch evidence.",
                            }
                        ]
                    },
                    "citations": [
                        {
                            "citation_id": "c1",
                            "source_name": "launch.pdf",
                            "page_label": "3",
                        }
                    ],
                },
            ],
        }
    }
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id

    try:
        html = save_latest_artifact_note_update(conversation_id)

        assert "Launch briefing" in html
        with Session(engine) as session:
            row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one()
        notes = row.data_source[NOTEBOOK_KEY]["notes"]
        assert len(notes) == 1
        assert notes[0]["title"] == "Launch briefing"
        assert "Create an executive briefing." in notes[0]["text"]
        assert "launch.pdf p.3" in notes[0]["text"]
    finally:
        _cleanup_conversation(conversation_id)


def test_save_latest_answer_note_update_persists_answer_note_and_refreshes_panel():
    conversation = Conversation(user="user-1")
    conversation.data_source = {
        NOTEBOOK_KEY: {
            "selected_source_ids": [],
            "notes": [],
            "artifacts": [],
        }
    }
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id

    try:
        html = save_latest_answer_note_update(
            conversation_id,
            [("Question one", ""), ("Question two", "Grounded answer.")],
            ["", "citation block"],
        )

        assert "1 saved" in html
        with Session(engine) as session:
            row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one()
        note = row.data_source[NOTEBOOK_KEY]["notes"][0]
        assert note["source"] == "answer"
        assert note["title"] == "Latest answer"
        assert note["text"] == "Grounded answer."
        assert note["citation_refs"] == ["citation block"]
    finally:
        _cleanup_conversation(conversation_id)


def test_save_manual_note_update_persists_note_and_refreshes_panel():
    conversation = Conversation(user="user-1")
    conversation.data_source = {
        NOTEBOOK_KEY: {
            "selected_source_ids": ["file-1"],
            "notes": [],
            "artifacts": [],
        }
    }
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id

    try:
        html = save_manual_note_update(
            conversation_id,
            "Manual insight",
            "This note should be available for artifact generation.",
        )

        assert "Manual insight" in html
        with Session(engine) as session:
            row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one()
        notes = row.data_source[NOTEBOOK_KEY]["notes"]
        assert notes[0]["title"] == "Manual insight"
        assert notes[0]["text"] == (
            "This note should be available for artifact generation."
        )
        assert notes[0]["source"] == "manual"
    finally:
        _cleanup_conversation(conversation_id)
