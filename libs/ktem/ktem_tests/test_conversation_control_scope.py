from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import gradio as gr
import ktem.pages.chat.control as control_module
import pytest
from gradio.helpers import special_args
from ktem.db.models import Conversation, engine
from ktem.pages.chat.control import ConversationControl
from sqlmodel import Session, select


def _conversation(*, user: str, name: str, public: bool = False) -> Conversation:
    row = Conversation(user=user, name=name, is_public=public)
    row.data_source = {
        "origin": "web",
        "messages": [["question", "answer"]],
        "retrieval_messages": ["refs"],
        "selected": {"9": ["select", ["file-1"], user]},
    }
    with Session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def _control() -> ConversationControl:
    control = cast(ConversationControl, object.__new__(ConversationControl))
    control._app = SimpleNamespace(index_manager=SimpleNamespace(indices=[]))
    return control


def _delete_rows(*conversation_ids: str) -> None:
    with Session(engine) as session:
        for conversation_id in conversation_ids:
            row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if row is not None:
                session.delete(row)
        session.commit()


@pytest.fixture
def password_identity(monkeypatch):
    request = cast(gr.Request, SimpleNamespace(username="attacker"))
    monkeypatch.setattr(control_module.flowsettings, "MARA_AUTH_MODE", "password")
    monkeypatch.setattr(
        control_module,
        "resolve_request_user_id",
        lambda received, *, auth_mode: (
            "attacker-id"
            if received is request and auth_mode == "password"
            else None
        ),
        raising=False,
    )
    return request


def test_control_cannot_select_private_session_with_forged_user(password_identity):
    row = _conversation(user="victim-id", name="Private")
    control = _control()

    try:
        selected = control.select_conv(row.id, "victim-id", password_identity)

        assert selected[0] == ""
        assert selected[1] == ""
        assert selected[3] == []
    finally:
        _delete_rows(row.id)


def test_control_can_read_public_session_without_owner_selection(password_identity):
    row = _conversation(user="victim-id", name="Public", public=True)
    control = _control()

    try:
        selected = control.select_conv(row.id, "victim-id", password_identity)

        assert selected[0] == row.id
        assert selected[2] == "Public"
        assert selected[3] == [["question", "answer"]]
        assert selected[5] == "refs"
    finally:
        _delete_rows(row.id)


@pytest.mark.parametrize("operation", ["delete", "rename"])
def test_control_rejects_private_session_mutation_with_forged_user(
    password_identity,
    operation,
):
    row = _conversation(user="victim-id", name="Protected")
    control = _control()

    try:
        with pytest.raises(gr.Error, match="owner scope"):
            if operation == "delete":
                control.delete_conv(row.id, "victim-id", password_identity)
            else:
                control.rename_conv(
                    row.id,
                    "Stolen",
                    True,
                    "victim-id",
                    password_identity,
                )

        with Session(engine) as session:
            unchanged = session.exec(
                select(Conversation).where(Conversation.id == row.id)
            ).one()
        assert unchanged.name == "Protected"
    finally:
        _delete_rows(row.id)


def test_control_new_session_uses_server_identity(password_identity):
    control = _control()
    created_id = ""

    try:
        created_id, _update = control.new_conv("victim-id", password_identity)

        with Session(engine) as session:
            created = session.exec(
                select(Conversation).where(Conversation.id == created_id)
            ).one()
        assert created.user == "attacker-id"
    finally:
        if created_id:
            _delete_rows(created_id)


def test_gradio_injects_control_request_without_component_input_changes(
    password_identity,
):
    control = _control()
    component_inputs = ["conversation-1", "claimed-user"]

    resolved_inputs, _progress_index, _event_data_index = special_args(
        control.select_conv,
        inputs=list(component_inputs),
        request=password_identity,
    )

    assert resolved_inputs[:2] == component_inputs
    assert resolved_inputs[2] is password_identity


def test_control_trusted_local_direct_calls_keep_optional_request(monkeypatch):
    row = _conversation(user="local-user", name="Local")
    control = _control()
    monkeypatch.setattr(control_module.flowsettings, "MARA_AUTH_MODE", "local")

    try:
        assert control.load_chat_history("local-user") == [("Local", row.id)]
        assert control.select_conv(row.id, "local-user")[0] == row.id
    finally:
        _delete_rows(row.id)


def test_control_network_direct_call_without_request_fails_closed(
    monkeypatch,
):
    row = _conversation(user="victim-id", name="Private")
    control = _control()
    monkeypatch.setattr(control_module.flowsettings, "MARA_AUTH_MODE", "password")

    try:
        with pytest.raises(gr.Error, match="Authenticated user identity is unavailable"):
            control.select_conv(row.id, "victim-id")
    finally:
        _delete_rows(row.id)
