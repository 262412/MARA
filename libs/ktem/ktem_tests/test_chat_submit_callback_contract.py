"""Preserve request identity, session access and all twelve callback outputs."""

from types import SimpleNamespace
from typing import Any, cast

import gradio as gr
import pytest
from ktem.pages import chat as page_module
from ktem.pages.chat import ChatPage

from .chat_submission_test_helpers import SubmissionProbe


@pytest.fixture
def callback(monkeypatch):
    probe = SubmissionProbe(monkeypatch)
    page = cast(Any, object.__new__(ChatPage))
    request = SimpleNamespace(username="authenticated")
    monkeypatch.setattr(
        page_module.flowsettings, "MARA_AUTH_MODE", "password", raising=False
    )
    monkeypatch.setattr(page_module, "KH_DEMO_MODE", False)
    monkeypatch.setattr(page_module, "DEFAULT_QUESTION", "Default question")

    def identity(req, *, auth_mode):
        probe.record("auth", (req,), {"auth_mode": auth_mode})
        return "owner"

    def rate_limit(kind, req):
        probe.record("rate_limit", (kind, req))
        return "unrelated-sso-id"

    update = {
        "value": "created",
        "choices": [("New conversation", "created")],
        "__type__": "update",
    }

    def new_conv(user, req):
        probe.record("new_conv", (user, req))
        return "created", update

    class NameResult:
        def one(self):
            probe.record("one")
            return SimpleNamespace(name="New conversation")

    class NameSession:
        def __init__(self, engine):
            probe.record("session", (engine,))

        def __enter__(self):
            probe.record("session_enter")
            return self

        def exec(self, statement):
            probe.record("query", (statement,))
            return NameResult()

        def __exit__(self, *error):
            probe.record("session_exit", error)

    monkeypatch.setattr(page_module, "resolve_request_user_id", identity)
    monkeypatch.setattr(page_module, "check_rate_limit", rate_limit)
    monkeypatch.setattr(page_module, "Session", NameSession)
    page.first_indexing_file_fn = probe.index_files
    page.first_indexing_url_fn = probe.index_urls
    page.merge_graph_source_ids = probe.merge_graph
    page.chat_control = SimpleNamespace(new_conv=new_conv)

    def submit(*, conv_id="existing", conv_name="Existing name", chat_input=None):
        values = probe.arguments()
        return page.submit_msg(
            values["chat_input"] if chat_input is None else chat_input,
            probe.history,
            "spoofed-ui-user",
            probe.settings,
            conv_id,
            conv_name,
            probe.choices,
            values["graph_source_ids"],
            values["selected_page_text"],
            probe.context,
            request=request,
        )

    return SimpleNamespace(
        probe=probe, page=page, request=request, submit=submit, update=update
    )


def test_existing_conversation_keeps_complete_twelve_output_contract(callback):
    result = callback.submit()
    probe = callback.probe
    text = "Ask\n\n[Selected text from current page]\nSelected evidence"
    assert result == [
        {},
        [["old question", "old answer"], (text, None)],
        "existing",
        {"__type__": "update"},
        "Existing name",
        "select",
        {
            "value": ["upload-id", "url-id"],
            "choices": probe.choices,
            "__type__": "update",
        },
        text,
        None,
        "Selected evidence",
        probe.context,
        ["merged-graph"],
    ]
    assert len(result) == 12 and type(result) is list
    assert result[1][0] is probe.history[0]
    assert result[6]["choices"] is probe.choices
    assert result[10] is probe.context and result[11] is probe.graph_result
    assert probe.names[0] == "auth" and "new_conv" not in probe.names
    assert probe.call("index_files")[1][-1] == "owner"
    assert probe.call("auth")[1][0] is callback.request


def test_new_session_access_occurs_after_preparation(callback):
    result = callback.submit(conv_id="")
    probe = callback.probe
    assert result[2:5] == ["created", callback.update, "New conversation"]
    assert result[3] is callback.update
    assert probe.names[-6:] == [
        "new_conv",
        "session",
        "session_enter",
        "query",
        "one",
        "session_exit",
    ]
    assert probe.call("new_conv")[1] == ("owner", callback.request)
    statement = probe.call("query")[1][0].compile()
    assert list(statement.params.values()) == ["created"]
    assert probe.names.index("append_history") < probe.names.index("new_conv")


@pytest.mark.parametrize(
    "conv_id,expected",
    [
        ("", [None, {"__type__": "update"}, None]),
        ("existing", ["existing", {"__type__": "update"}, "Existing name"]),
    ],
)
def test_demo_rate_limit_precedes_index_and_never_creates_session(
    callback, monkeypatch, conv_id, expected
):
    monkeypatch.setattr(page_module, "KH_DEMO_MODE", True)
    result = callback.submit(conv_id=conv_id)
    assert result[2:5] == expected
    assert callback.probe.names[:3] == ["auth", "rate_limit", "sources"]
    assert callback.probe.call("index_files")[1][-1] == "owner"
    assert "new_conv" not in callback.probe.names


@pytest.mark.parametrize(
    "stage",
    ["auth", "rate_limit", "index_files", "merge_graph", "selection", "append_history"],
)
def test_failures_before_session_preserve_auth_limit_and_short_circuit(
    callback, monkeypatch, stage
):
    monkeypatch.setattr(page_module, "KH_DEMO_MODE", True)
    callback.probe.fail_at = stage
    with pytest.raises(RuntimeError) as caught:
        callback.submit(conv_id="")
    assert caught.value is callback.probe.failure
    assert callback.probe.names[-1] == stage
    assert "new_conv" not in callback.probe.names
    if stage in {"auth", "rate_limit"}:
        assert "sources" not in callback.probe.names


@pytest.mark.parametrize(
    "stage,tail",
    [
        ("new_conv", ["new_conv"]),
        ("session", ["new_conv", "session"]),
        ("session_enter", ["new_conv", "session", "session_enter"]),
        ("query", ["new_conv", "session", "session_enter", "query", "session_exit"]),
        (
            "one",
            ["new_conv", "session", "session_enter", "query", "one", "session_exit"],
        ),
    ],
)
def test_session_errors_keep_access_order_and_context_cleanup(callback, stage, tail):
    callback.probe.fail_at = stage
    with pytest.raises(RuntimeError) as caught:
        callback.submit(conv_id="")
    assert caught.value is callback.probe.failure
    names = callback.probe.names
    assert names[names.index("new_conv") :] == tail


def test_missing_authenticated_identity_rejects_before_preparation(
    callback, monkeypatch
):
    monkeypatch.setattr(page_module, "resolve_request_user_id", lambda *a, **k: None)
    with pytest.raises(gr.Error) as caught:
        callback.submit()
    assert caught.value.message == "Authenticated user identity is unavailable."
    assert callback.probe.names == []


def test_empty_input_is_checked_after_identity_and_rate_limit(callback, monkeypatch):
    monkeypatch.setattr(page_module, "KH_DEMO_MODE", True)
    with pytest.raises(ValueError, match="^Input is empty$"):
        callback.submit(chat_input={})
    assert callback.probe.names == ["auth", "rate_limit"]


def test_submit_resolves_legacy_preparation_patch_at_call_time(callback, monkeypatch):
    def patched(**kwargs):
        assert kwargs["user_id"] == "owner"
        raise callback.probe.failure

    monkeypatch.setattr(page_module, "prepare_chat_submission", patched)
    with pytest.raises(RuntimeError) as caught:
        callback.submit()
    assert caught.value is callback.probe.failure
    assert callback.probe.names == ["auth"]
