from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import gradio as gr
import ktem.pages.chat as chat_module
import pytest
from ktem.pages.chat import ChatPage


class _RuntimeSpy:
    def __init__(self) -> None:
        self.calls = []

    def persist_conversation_state(self, **kwargs):
        self.calls.append(kwargs)
        return ["refs"], ["plot"]


def _page():
    page = cast(Any, object.__new__(ChatPage))
    runtime = _RuntimeSpy()
    resolved_users = []
    page.docqa = runtime
    page.file_index = SimpleNamespace(
        id=9,
        resolve_selected_ids=lambda user_id, selected: (
            resolved_users.append((user_id, selected)) or ["file-1"]
        ),
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
        ["select", ["file-1"], claimed_user],
        request=request,
    )


@pytest.mark.parametrize("auth_mode", ["password", "sso"])
def test_chat_persist_ignores_forged_hidden_user_in_network_auth(
    monkeypatch,
    auth_mode,
):
    page, runtime, resolved_users = _page()
    request = cast(gr.Request, SimpleNamespace(username="alice"))
    identity_calls = []
    monkeypatch.setattr(chat_module.flowsettings, "MARA_AUTH_MODE", auth_mode)
    monkeypatch.setattr(
        chat_module,
        "resolve_request_user_id",
        lambda received, *, auth_mode: (
            identity_calls.append((received, auth_mode)) or "server-user"
        ),
    )

    result = _persist(page, request=request)

    assert result == (["refs"], ["plot"])
    assert identity_calls == [(request, auth_mode)]
    assert resolved_users == [
        ("server-user", (["select", ["file-1"], "forged-owner"],))
    ]
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

    assert resolved_users == [
        ("default", (["select", ["file-1"], "default"],))
    ]
    assert runtime.calls[0]["user_id"] == "default"
