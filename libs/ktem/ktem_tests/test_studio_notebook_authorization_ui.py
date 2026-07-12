from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import cast

import gradio as gr
import pytest
from gradio.helpers import special_args
from ktem.db.models import Conversation, engine
from ktem.docqa import _runtime_notebook as notebook
from ktem.pages.chat.studio_artifacts import (
    export_latest_artifact_update,
    render_conversation_notebook_panel_html,
)
from ktem.pages.chat.studio_callback_identity import bind_page_callback
from ktem.pages.chat.studio_note_actions import (
    convert_note_to_source_update,
    save_manual_note_update,
)
from sqlmodel import Session, select


@pytest.fixture()
def private_notebook():
    data_source, _note = notebook.add_note(
        {"private_marker": "PRIVATE-NOTEBOOK-MARKER"},
        title="Private note",
        text="owner only",
        note_id="note-1",
    )
    data_source, _artifact = notebook.save_artifact(
        data_source,
        artifact_type="briefing_doc",
        payload={"marker": "PRIVATE-ARTIFACT-MARKER"},
        artifact_id="artifact-1",
    )
    conversation = Conversation(user="owner-1", is_public=False)
    conversation.data_source = data_source
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id
    yield conversation_id
    with Session(engine) as session:
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


def _page(resolved_user_id: str, *, index_paths=None):
    runtime = SimpleNamespace(
        _resolve_user_id=lambda: "forged-runtime-user",
        index_paths=index_paths,
    )
    return SimpleNamespace(
        docqa=runtime,
        _resolve_persist_user_id=lambda _fallback, _request: resolved_user_id,
    )


def test_bound_note_callback_injects_exact_request_without_component_port(
    private_notebook,
):
    request = cast(gr.Request, SimpleNamespace(username="owner"))
    callback = bind_page_callback(save_manual_note_update, _page("owner-1"))
    component_inputs = [private_notebook, "Server note", "server-owned text"]

    resolved, _progress, _event_data = special_args(
        callback,
        inputs=list(component_inputs),
        request=request,
    )

    assert resolved[:3] == component_inputs
    assert resolved[3] is request
    callback(*resolved)
    saved = notebook.get_notebook(private_notebook, user_id="owner-1")
    assert saved["notes"][-1]["text"] == "server-owned text"


def test_bound_note_callback_maps_denial_to_neutral_gradio_error(
    private_notebook,
):
    request = cast(gr.Request, SimpleNamespace(username="attacker"))
    callback = bind_page_callback(save_manual_note_update, _page("attacker"))
    before = _data_source(private_notebook)

    with pytest.raises(gr.Error, match="Notebook is unavailable"):
        callback(private_notebook, "Attacker", "must not persist", request)

    assert _data_source(private_notebook) == before


def test_denied_note_conversion_precedes_materialize_and_index(
    private_notebook,
    monkeypatch,
):
    materialized: list[str] = []
    indexed: list[str] = []
    monkeypatch.setattr(
        notebook,
        "materialize_note_source",
        lambda *_args, **_kwargs: materialized.append("called"),
    )
    page = _page(
        "attacker",
        index_paths=lambda *_args, **_kwargs: indexed.append("called"),
    )
    callback = bind_page_callback(convert_note_to_source_update, page)

    with pytest.raises(gr.Error, match="Notebook is unavailable"):
        callback(private_notebook, "note-1", SimpleNamespace(username="attacker"))

    assert materialized == []
    assert indexed == []


def test_denied_export_precedes_output_file_creation(private_notebook, tmp_path):
    before = _data_source(private_notebook)

    with pytest.raises(notebook.NotebookAccessError):
        export_latest_artifact_update(
            private_notebook,
            root_dir=tmp_path,
            user_id="attacker",
        )

    assert not list(tmp_path.rglob("*"))
    assert _data_source(private_notebook) == before


def test_public_render_is_explicit_and_private_render_is_neutral(private_notebook):
    hidden = render_conversation_notebook_panel_html(
        private_notebook,
        user_id="reader",
    )
    assert "owner only" not in hidden

    with Session(engine) as session:
        row = session.exec(
            select(Conversation).where(Conversation.id == private_notebook)
        ).one()
        row.is_public = True
        session.add(row)
        session.commit()

    visible = render_conversation_notebook_panel_html(
        private_notebook,
        user_id="reader",
    )
    assert "Private note" in visible
