from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import gradio as gr
import ktem.pages.chat as chat_module
import pytest
from gradio.helpers import special_args
from ktem.pages.chat import ChatPage


class _RuntimeSpy:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def persist_conversation_state(self, **kwargs):
        self.calls.append(kwargs)
        return ["refs"], ["plot"]


def _page():
    page = cast(Any, object.__new__(ChatPage))
    runtime = _RuntimeSpy()
    resolved_users: list[tuple[str, Any]] = []

    def resolve_selected_ids(user_id, selected):
        resolved_users.append((user_id, selected))
        return ["file-1"]

    page.docqa = runtime
    page.file_index = SimpleNamespace(
        id=9,
        resolve_selected_ids=resolve_selected_ids,
    )
    page._build_selected_input_map = lambda *selecteds: {9: list(selecteds)}
    page._normalize_selected_file_ids = lambda values: list(values or [])
    return page, runtime, resolved_users


def _persist(page, *, request, claimed_user="forged-owner"):
    return page.persist_data_source(
        "conversation-1",
        claimed_user,
        "refs",
        None,
        [],
        [],
        [("question", "answer")],
        {"app": {"regen": False}},
        ["file-1"],
        request,
        ["select", ["file-1"], claimed_user],
    )


@pytest.mark.parametrize("auth_mode", ["password", "sso"])
def test_chat_persist_ignores_forged_hidden_user_in_network_auth(
    monkeypatch,
    auth_mode,
):
    page, runtime, resolved_users = _page()
    request = cast(gr.Request, SimpleNamespace(username="alice"))
    identity_calls: list[tuple[Any, str]] = []

    def resolve_identity(received, *, auth_mode):
        identity_calls.append((received, auth_mode))
        return "server-user"

    monkeypatch.setattr(chat_module.flowsettings, "MARA_AUTH_MODE", auth_mode)
    monkeypatch.setattr(
        chat_module,
        "resolve_request_user_id",
        resolve_identity,
    )

    result = _persist(page, request=request)

    assert result == (["refs"], ["plot"])
    assert identity_calls == [(request, auth_mode)]
    assert resolved_users == [("server-user", [["select", ["file-1"], "forged-owner"]])]
    assert runtime.calls[0]["user_id"] == "server-user"


def test_chat_persist_rejects_missing_server_identity(monkeypatch):
    page, runtime, _resolved_users = _page()
    monkeypatch.setattr(chat_module.flowsettings, "MARA_AUTH_MODE", "password")
    monkeypatch.setattr(
        chat_module,
        "resolve_request_user_id",
        lambda _request, *, auth_mode: None,
    )

    with pytest.raises(gr.Error, match="Authenticated user identity is unavailable"):
        _persist(page, request=cast(gr.Request, SimpleNamespace(username="")))

    assert runtime.calls == []


def test_chat_persist_keeps_local_identity_behavior(monkeypatch):
    page, runtime, resolved_users = _page()
    monkeypatch.setattr(chat_module.flowsettings, "MARA_AUTH_MODE", "local")
    monkeypatch.setattr(
        chat_module,
        "resolve_request_user_id",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
        raising=False,
    )

    _persist(page, request=None, claimed_user="default")

    assert resolved_users == [("default", [["select", ["file-1"], "default"]])]
    assert runtime.calls[0]["user_id"] == "default"


def test_gradio_injects_request_without_changing_component_input_order():
    page, _runtime, _resolved_users = _page()
    request = cast(gr.Request, SimpleNamespace(username="alice"))
    component_inputs = [
        "conversation-1",
        "claimed-user",
        "refs",
        None,
        [],
        [],
        [("question", "answer")],
        {"app": {"regen": False}},
        ["file-1"],
        ["select", ["file-1"], "claimed-user"],
    ]
    original_inputs = list(component_inputs)

    resolved_inputs, _progress_index, _event_data_index = special_args(
        page.persist_data_source,
        inputs=component_inputs,
        request=request,
    )

    assert resolved_inputs[:9] == original_inputs[:9]
    assert resolved_inputs[9] is request
    assert resolved_inputs[10:] == original_inputs[9:]
