from ktem.db.models import Conversation, engine
from ktem.docqa._runtime_notebook import (
    NOTEBOOK_KEY,
    add_note,
    add_note_to_conversation,
    build_source_guides,
    get_artifact,
    get_notebook,
    list_artifacts,
    list_notes,
    materialize_note_source,
    record_note_indexed_source,
    save_answer_as_note,
    save_artifact,
    save_artifact_to_conversation,
    select_conversation_sources,
    set_selected_sources,
)
from ktem.docqa.artifact_evaluation import evaluate_artifact_collection
from sqlmodel import Session, select


def test_notebook_source_selection_syncs_graph_source_ids_and_dedupes():
    updated = set_selected_sources(
        {"origin": "cli", "graph_source_ids": ["old-source"]},
        ["file-1", "", "file-2", "file-1"],
    )

    assert updated["origin"] == "cli"
    assert updated["graph_source_ids"] == ["file-1", "file-2"]
    assert updated[NOTEBOOK_KEY]["selected_source_ids"] == ["file-1", "file-2"]


def test_notebook_notes_are_created_with_stable_shape_and_listed():
    updated, note = add_note(
        {},
        title="Research note",
        text="MARA should keep source-backed notes.",
        note_id="note-1",
        timestamp="2026-05-31T12:00:00+00:00",
    )

    assert note == {
        "note_id": "note-1",
        "title": "Research note",
        "text": "MARA should keep source-backed notes.",
        "source": "manual",
        "citation_refs": [],
        "created_at": "2026-05-31T12:00:00+00:00",
        "updated_at": "2026-05-31T12:00:00+00:00",
    }
    assert list_notes(updated) == [note]


def test_notebook_can_save_answer_notes_with_citations():
    updated, note = save_answer_as_note(
        {},
        answer="The evidence supports the claim.",
        title="Grounded answer",
        citation_refs=["file-1:3", "file-2:7"],
        note_id="answer-1",
        timestamp="2026-05-31T12:01:00+00:00",
    )

    assert note["source"] == "answer"
    assert note["citation_refs"] == ["file-1:3", "file-2:7"]
    assert list_notes(updated) == [note]


def test_notebook_artifacts_are_saved_without_losing_notes():
    with_note, note = add_note(
        {},
        title="Source note",
        text="Preserve this note.",
        note_id="note-1",
        timestamp="2026-05-31T12:00:00+00:00",
    )

    updated, artifact = save_artifact(
        with_note,
        artifact_type="quiz",
        payload={"questions": []},
        artifact_id="artifact-1",
        timestamp="2026-05-31T12:02:00+00:00",
    )

    assert list_notes(updated) == [note]
    assert artifact["artifact_id"] == "artifact-1"
    assert artifact["type"] == "quiz"
    assert artifact["payload"] == {"questions": []}
    assert artifact["status"] == "ready"
    assert artifact["title"] == "Quiz"
    assert artifact["source_scope"] == {"mode": "document", "source_ids": []}
    assert artifact["created_at"] == "2026-05-31T12:02:00+00:00"
    assert artifact["updated_at"] == "2026-05-31T12:02:00+00:00"
    assert updated[NOTEBOOK_KEY]["artifacts"] == [artifact]


def test_notebook_note_can_be_materialized_and_marked_as_indexed_source(tmp_path):
    with_note, note = add_note(
        {"graph_source_ids": ["file-1"]},
        title="Key finding",
        text="This note should become retrievable source material.",
        note_id="note-1",
        timestamp="2026-05-31T12:00:00+00:00",
    )

    source_path = materialize_note_source("conv-1", note, tmp_path)
    updated, updated_note = record_note_indexed_source(
        with_note,
        "note-1",
        source_ids=["file-note-1"],
        source_path=source_path,
        timestamp="2026-05-31T12:05:00+00:00",
    )

    assert source_path.endswith("conv-1/mara-note-note-1.md")
    assert "Note ID: note-1" in (tmp_path / "conv-1" / "mara-note-note-1.md").read_text(
        encoding="utf-8"
    )
    assert "This note should become retrievable source material." in (
        tmp_path / "conv-1" / "mara-note-note-1.md"
    ).read_text(encoding="utf-8")
    assert updated_note["indexed_source_ids"] == ["file-note-1"]
    assert updated_note["indexed_source_path"] == source_path
    assert updated_note["indexed_at"] == "2026-05-31T12:05:00+00:00"
    assert updated[NOTEBOOK_KEY]["selected_source_ids"] == ["file-1", "file-note-1"]
    assert updated["graph_source_ids"] == ["file-1", "file-note-1"]


def test_source_guide_summarizes_indexed_file_metadata():
    guides = build_source_guides(
        [
            {
                "file_id": "file-1",
                "name": "Alpha Report.pdf",
                "tokens": 1200,
                "size": 4096,
                "loader": "pdf",
                "path": "D:/docs/alpha.pdf",
                "date_created": "2026-05-31T12:00:00",
            }
        ]
    )

    assert guides == [
        {
            "source_id": "file-1",
            "name": "Alpha Report.pdf",
            "summary": "Alpha Report.pdf is an indexed pdf source with 1200 tokens.",
            "key_topics": ["Alpha", "Report"],
            "suggested_questions": [
                "What are the key points in Alpha Report.pdf?",
                "Which evidence from Alpha Report.pdf supports the answer?",
            ],
            "metadata": {
                "tokens": 1200,
                "size": 4096,
                "loader": "pdf",
                "path": "D:/docs/alpha.pdf",
                "date_created": "2026-05-31T12:00:00",
            },
        }
    ]


def test_conversation_notebook_notes_are_persisted():
    conversation = Conversation(user="user-1")
    conversation.data_source = {"origin": "cli"}
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id

    try:
        note = add_note_to_conversation(
            conversation_id,
            user_id="user-1",
            title="Manual note",
            text="Persist this note.",
            note_id="note-1",
            timestamp="2026-05-31T12:03:00+00:00",
        )
        notebook = get_notebook(conversation_id, user_id="user-1")

        assert notebook["notes"] == [note]
        assert note["source"] == "manual"
    finally:
        with Session(engine) as session:
            cleanup_row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if cleanup_row is not None:
                session.delete(cleanup_row)
                session.commit()


def test_conversation_source_selection_is_persisted():
    conversation = Conversation(user="user-1")
    conversation.data_source = {"origin": "cli"}
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id

    try:
        selected = select_conversation_sources(
            conversation_id,
            ["file-2", "file-1", "file-2"],
            user_id="user-1",
        )

        assert selected == ["file-2", "file-1"]
        assert get_notebook(conversation_id, user_id="user-1")[
            "selected_source_ids"
        ] == [
            "file-2",
            "file-1",
        ]
        with Session(engine) as session:
            row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one()
        assert row.data_source["graph_source_ids"] == ["file-2", "file-1"]
    finally:
        with Session(engine) as session:
            cleanup_row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if cleanup_row is not None:
                session.delete(cleanup_row)
                session.commit()


def test_conversation_artifact_is_persisted_to_notebook():
    conversation = Conversation(user="user-1")
    conversation.data_source = {"origin": "cli"}
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id

    try:
        artifact = save_artifact_to_conversation(
            conversation_id,
            user_id="user-1",
            artifact_type="study_guide",
            payload={"sections": []},
            artifact_id="artifact-1",
            timestamp="2026-05-31T12:06:00+00:00",
        )

        assert artifact["artifact_id"] == "artifact-1"
        assert artifact["type"] == "study_guide"
        assert artifact["payload"] == {"sections": []}
        assert artifact["status"] == "ready"
        assert artifact["title"] == "Study Guide"
        assert artifact["created_at"] == "2026-05-31T12:06:00+00:00"
        assert artifact["updated_at"] == "2026-05-31T12:06:00+00:00"
        assert get_notebook(conversation_id, user_id="user-1")["artifacts"] == [
            artifact
        ]
        assert list_artifacts(
            {NOTEBOOK_KEY: get_notebook(conversation_id, user_id="user-1")}
        ) == [artifact]
        assert (
            get_artifact(
                {NOTEBOOK_KEY: get_notebook(conversation_id, user_id="user-1")},
                "artifact-1",
            )
            == artifact
        )
    finally:
        with Session(engine) as session:
            cleanup_row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if cleanup_row is not None:
                session.delete(cleanup_row)
                session.commit()


def test_cross_format_artifacts_survive_reload_for_collection_evaluation():
    conversation = Conversation(user="user-1")
    conversation.data_source = {"origin": "cli"}
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id

    try:
        save_artifact_to_conversation(
            conversation_id,
            user_id="user-1",
            artifact_type="study_guide",
            payload={"overview": "Grounded overview."},
            artifact_id="artifact-1",
            source_scope={"mode": "multi-document", "source_ids": ["pdf", "pptx"]},
            citations=[
                {"citation_id": "c1", "source_id": "pdf", "source_name": "a.pdf"},
                {"citation_id": "c2", "source_id": "pptx", "source_name": "b.pptx"},
            ],
        )
        save_artifact_to_conversation(
            conversation_id,
            user_id="user-1",
            artifact_type="quiz",
            payload={"multiple_choice": []},
            artifact_id="artifact-2",
            source_scope={"mode": "multi-document", "source_ids": ["docx", "image"]},
            citations=[
                {"citation_id": "c3", "source_id": "docx", "source_name": "c.docx"},
                {"citation_id": "c4", "source_id": "image", "source_name": "d.png"},
            ],
        )

        report = evaluate_artifact_collection(
            get_notebook(conversation_id, user_id="user-1")["artifacts"]
        )

        assert report["artifact_count"] == 2
        assert set(report["source_format_summary"]) == {"docx", "image", "pdf", "pptx"}
    finally:
        with Session(engine) as session:
            cleanup_row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if cleanup_row is not None:
                session.delete(cleanup_row)
                session.commit()
