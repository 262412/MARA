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


class _SessionRuntimeSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def set_session_public(self, conversation_id, is_public, user_id=None):
        self.calls.append(("set_public", conversation_id, is_public, user_id))
        return "Conversation"

    def load_graph_source_ids(self, conversation_id, user_id=None):
        self.calls.append(("load_graph", conversation_id, user_id))
        return ["file-1"]

    def persist_graph_source_ids(self, conversation_id, source_ids, user_id=None):
        self.calls.append(("persist_graph", conversation_id, list(source_ids), user_id))
        return list(source_ids)

    def append_session_like(
        self,
        conversation_id,
        index,
        value,
        liked,
        user_id=None,
    ):
        self.calls.append(("like", conversation_id, index, value, liked, user_id))


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


def test_gradio_injects_chat_runtime_request_before_dynamic_index_inputs():
    page, _runtime, _resolved_users = _page()
    request = cast(gr.Request, SimpleNamespace(username="alice"))
    fixed_inputs = list(range(22))
    selected_input = ["select", ["file-1"], "claimed-user"]
    component_inputs = [*fixed_inputs, selected_input]

    resolved_inputs, _progress_index, _event_data_index = special_args(
        page.chat_fn,
        inputs=list(component_inputs),
        request=request,
    )

    assert resolved_inputs[:22] == fixed_inputs
    assert resolved_inputs[22] is request
    assert resolved_inputs[23:] == [selected_input]


def test_chat_session_metadata_callbacks_delegate_server_identity(monkeypatch):
    page = cast(Any, object.__new__(ChatPage))
    runtime = _SessionRuntimeSpy()
    page.docqa = runtime
    page._normalize_selected_file_ids = lambda values: list(values or [])
    request = cast(gr.Request, SimpleNamespace(username="alice"))
    monkeypatch.setattr(chat_module.flowsettings, "MARA_AUTH_MODE", "password")
    monkeypatch.setattr(
        chat_module,
        "resolve_request_user_id",
        lambda received, *, auth_mode: (
            "server-user" if received is request and auth_mode == "password" else None
        ),
    )
    liked = SimpleNamespace(index=[0, 1], value="answer", liked=True)

    page.on_set_public_conversation(True, "conversation-1", "forged", request)
    assert page.load_conversation_graph_state("conversation-1", "forged", request) == [
        "file-1"
    ]
    assert page.persist_conversation_source_scope(
        "conversation-1", "forged", ["file-1"], request
    ) == ["file-1"]
    page.is_liked("conversation-1", liked, "forged", request)

    assert runtime.calls == [
        ("set_public", "conversation-1", True, "server-user"),
        ("load_graph", "conversation-1", "server-user"),
        ("persist_graph", "conversation-1", ["file-1"], "server-user"),
        ("like", "conversation-1", [0, 1], "answer", True, "server-user"),
    ]


def test_chat_session_metadata_callbacks_reject_missing_server_identity(monkeypatch):
    page = cast(Any, object.__new__(ChatPage))
    runtime = _SessionRuntimeSpy()
    page.docqa = runtime
    page._normalize_selected_file_ids = lambda values: list(values or [])
    monkeypatch.setattr(chat_module.flowsettings, "MARA_AUTH_MODE", "password")
    monkeypatch.setattr(
        chat_module,
        "resolve_request_user_id",
        lambda _request, *, auth_mode: None,
    )

    with pytest.raises(gr.Error, match="Authenticated user identity is unavailable"):
        page.on_set_public_conversation(True, "conversation-1", "forged", None)

    assert runtime.calls == []


def test_gradio_injects_rerun_request_without_component_input_changes():
    page, _runtime, _resolved_users = _page()
    request = cast(gr.Request, SimpleNamespace(username="alice"))
    fixed_inputs = list(range(16))
    selected_input = ["select", ["file-1"], "claimed-user"]
    component_inputs = [*fixed_inputs, selected_input]
    original_inputs = list(component_inputs)

    resolved_inputs, _progress_index, _event_data_index = special_args(
        page.rerun_page_answer,
        inputs=component_inputs,
        request=request,
    )

    assert resolved_inputs[:16] == original_inputs[:16]
    assert resolved_inputs[16] is request
    assert resolved_inputs[17:] == original_inputs[16:]


def test_gradio_injects_session_metadata_requests_without_component_inputs():
    page, _runtime, _resolved_users = _page()
    request = cast(gr.Request, SimpleNamespace(username="alice"))

    public_inputs, *_ = special_args(
        page.on_set_public_conversation,
        inputs=[True, "conversation-1"],
        request=request,
    )
    graph_inputs, *_ = special_args(
        page.load_conversation_graph_state,
        inputs=["conversation-1"],
        request=request,
    )
    persist_inputs, *_ = special_args(
        page.persist_conversation_source_scope,
        inputs=["conversation-1", "claimed-user", ["file-1"]],
        request=request,
    )
    like_inputs, *_ = special_args(
        page.is_liked,
        inputs=["conversation-1"],
        request=request,
        event_data=gr.EventData(
            None,
            {"index": [0, 1], "value": "answer", "liked": True},
        ),
    )

    assert public_inputs == [True, "conversation-1", None, request]
    assert graph_inputs == ["conversation-1", None, request]
    assert persist_inputs == [
        "conversation-1",
        "claimed-user",
        ["file-1"],
        request,
    ]
    assert like_inputs[0] == "conversation-1"
    assert isinstance(like_inputs[1], gr.LikeData)
    assert like_inputs[2:] == [None, request]


def test_rerun_page_answer_forwards_server_request_to_chat_runtime():
    page = cast(Any, object.__new__(ChatPage))
    request = cast(gr.Request, SimpleNamespace(username="alice"))
    selected = ["select", ["file-1"], "claimed-user"]
    calls = []

    def chat_fn(*args):
        calls.append(args)
        yield ("final",)

    page.chat_fn = chat_fn

    result = page.rerun_page_answer(
        "Question",
        "conversation-1",
        [],
        {},
        "mara",
        "model",
        False,
        "inline",
        "en",
        {"app": {"regen": False}},
        None,
        "claimed-user",
        "file-1",
        "alpha.pdf",
        1,
        "selected text",
        request,
        selected,
    )

    assert result == ("final",)
    assert calls[0][22] is request
    assert calls[0][23:] == (selected,)
