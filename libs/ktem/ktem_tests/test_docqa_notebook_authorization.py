from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, cast

import pytest
from ktem.db.models import Conversation, engine
from ktem.docqa import _runtime_notebook as notebook_module
from sqlmodel import Session, select

notebook = cast(Any, notebook_module)


@pytest.fixture()
def notebook_conversations():
    data_source, note = notebook.add_note(
        {"private_marker": "OWNER-ONLY-MARKER"},
        title="Private note",
        text="private note marker",
        note_id="note-1",
        timestamp="2026-07-12T00:00:00+00:00",
    )
    data_source, artifact = notebook.save_artifact(
        data_source,
        artifact_type="study_guide",
        payload={"marker": "PRIVATE-ARTIFACT-MARKER"},
        artifact_id="artifact-1",
        timestamp="2026-07-12T00:00:00+00:00",
    )
    private = Conversation(user="owner-1", is_public=False)
    private.data_source = deepcopy(data_source)
    public = Conversation(user="owner-1", is_public=True)
    public.data_source = deepcopy(data_source)
    with Session(engine) as session:
        session.add(private)
        session.add(public)
        session.commit()
        session.refresh(private)
        session.refresh(public)
        ids = (private.id, public.id)
    yield ids, note, artifact
    with Session(engine) as session:
        for conversation_id in ids:
            row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if row is not None:
                session.delete(row)
        session.commit()


def _data_source(conversation_id: str) -> dict:
    with Session(engine) as session:
        row = session.exec(
            select(Conversation).where(Conversation.id == conversation_id)
        ).one()
        return deepcopy(dict(row.data_source or {}))


def _access_error():
    return notebook.NotebookAccessError


def test_owner_can_read_and_mutate_notebook(notebook_conversations):
    (private_id, _public_id), _note, _artifact = notebook_conversations

    before = notebook.get_notebook(private_id, user_id="owner-1")
    saved = notebook.add_note_to_conversation(
        private_id,
        user_id="owner-1",
        title="Owner note",
        text="owner mutation",
        note_id="owner-note",
    )
    after = notebook.get_notebook(private_id, user_id="owner-1")

    assert before["notes"][0]["note_id"] == "note-1"
    assert saved["note_id"] == "owner-note"
    assert [item["note_id"] for item in after["notes"]] == [
        "note-1",
        "owner-note",
    ]


def test_private_notebook_read_hides_missing_and_non_owner_equally(
    notebook_conversations,
):
    (private_id, _public_id), _note, _artifact = notebook_conversations

    messages = []
    for conversation_id in (private_id, "missing-conversation"):
        with pytest.raises(_access_error()) as exc_info:
            notebook.get_notebook(conversation_id, user_id="attacker")
        messages.append(str(exc_info.value))

    assert messages[0] == messages[1]
    assert "missing" not in messages[0].lower()
    assert private_id not in messages[0]


def _mutation_cases() -> list[tuple[str, Callable[[str, str], object]]]:
    return [
        (
            "save artifact",
            lambda conversation_id, user_id: notebook.save_artifact_to_conversation(
                conversation_id,
                user_id=user_id,
                artifact_type="quiz",
                payload={"marker": "ATTACKER"},
                artifact_id="attacker-artifact",
            ),
        ),
        (
            "delete artifact",
            lambda conversation_id, user_id: notebook.delete_artifact_from_conversation(
                conversation_id, "artifact-1", user_id=user_id
            ),
        ),
        (
            "record export",
            lambda conversation_id, user_id: notebook.record_artifact_export_to_conversation(
                conversation_id,
                "artifact-1",
                user_id=user_id,
                export_format="html",
                path="/tmp/attacker.html",
            ),
        ),
        (
            "add note",
            lambda conversation_id, user_id: notebook.add_note_to_conversation(
                conversation_id,
                user_id=user_id,
                title="Attacker",
                text="ATTACKER NOTE",
            ),
        ),
        (
            "save answer",
            lambda conversation_id, user_id: notebook.save_answer_note_to_conversation(
                conversation_id,
                user_id=user_id,
                title="Attacker",
                answer="ATTACKER ANSWER",
            ),
        ),
        (
            "select sources",
            lambda conversation_id, user_id: notebook.select_conversation_sources(
                conversation_id, ["attacker-source"], user_id=user_id
            ),
        ),
        (
            "record indexed note",
            lambda conversation_id, user_id: notebook.record_note_indexed_source_to_conversation(
                conversation_id,
                "note-1",
                user_id=user_id,
                source_ids=["attacker-source"],
                source_path="/tmp/attacker.md",
            ),
        ),
    ]


@pytest.mark.parametrize("_name,mutation", _mutation_cases())
def test_each_notebook_mutation_rejects_non_owner_without_json_change(
    notebook_conversations,
    _name,
    mutation,
):
    (private_id, _public_id), _note, _artifact = notebook_conversations
    before = _data_source(private_id)

    with pytest.raises(_access_error()):
        mutation(private_id, "attacker")

    assert _data_source(private_id) == before


def test_public_notebook_read_requires_explicit_opt_in(notebook_conversations):
    (_private_id, public_id), _note, _artifact = notebook_conversations

    with pytest.raises(_access_error()):
        notebook.get_notebook(public_id, user_id="reader")

    visible = notebook.get_notebook(
        public_id,
        user_id="reader",
        allow_public=True,
    )
    assert visible["notes"][0]["text"] == "private note marker"


@pytest.mark.parametrize("_name,mutation", _mutation_cases())
def test_public_notebook_mutations_remain_owner_only(
    notebook_conversations,
    _name,
    mutation,
):
    (_private_id, public_id), _note, _artifact = notebook_conversations
    before = _data_source(public_id)

    with pytest.raises(_access_error()):
        mutation(public_id, "reader")

    assert _data_source(public_id) == before
