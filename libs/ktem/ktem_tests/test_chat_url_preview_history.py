"""URL fallbacks keep request authority; display never replaces completed history."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import gradio as gr
import pytest
from ktem.auth import service as auth
from ktem.db.models import User
from ktem.pages.chat import page_preview_callbacks, page_preview_resolver
from ktem.pages.chat.chat_docqa_streaming import _with_displayed_final_answer
from ktem.pages.chat.page_preview import ChatPagePreviewController
from ktem.pages.chat.page_preview_models import PreviewPayload
from ktem.preview.errors import PreviewAccessError
from sqlmodel import Session, SQLModel

from . import test_preview_owner_scope

owned_preview_app = test_preview_owner_scope.owned_preview_app


@pytest.fixture
def url_controller(monkeypatch, owned_preview_app):
    app, engine, storage = owned_preview_app
    SQLModel.metadata.create_all(engine)
    source = app.index_manager.indices[0]._resources["Source"]
    with Session(engine) as session:
        for owner in ("attacker", "victim"):
            session.add(
                User(
                    id=owner,
                    username=owner,
                    username_lower=owner,
                    password="unused",
                    admin=False,
                )
            )
            row = session.get(source, owner + "-file")
            assert row is not None
            row.name = "https://example.org/" + owner
            row.path = owner + "-missing-url-artifact"
        session.commit()
    monkeypatch.setattr(auth, "engine", engine)
    monkeypatch.setattr(page_preview_resolver, "engine", engine)
    monkeypatch.setattr(
        page_preview_callbacks.flowsettings, "MARA_AUTH_MODE", "password"
    )
    return ChatPagePreviewController(app), storage


def test_authenticated_url_without_local_artifact_is_an_explicit_notice(url_controller):
    controller, _ = url_controller
    request = gr.Request(username="attacker", session_hash="first-browser")
    result = controller.on_selected_file_change([], ["attacker-file"], {}, request)
    assert result[0] == "attacker-file"
    assert result[5] == ""
    assert "Selected file is unavailable" in result[6]


@pytest.mark.parametrize(
    "incoming", [None, gr.Request(), gr.Request(username="deleted")]
)
def test_missing_request_does_not_reuse_previous_url_authority(
    url_controller, incoming
):
    controller, _ = url_controller
    with pytest.raises(PreviewAccessError):
        controller.on_selected_file_change(
            [("forged owner", "attacker-file")],
            ["attacker-file"],
            {},
            incoming,
        )


def test_delayed_name_and_path_fallbacks_keep_each_authenticated_request(
    url_controller, monkeypatch
):
    controller, _ = url_controller
    service = controller._preview_payload_service
    build = service.build_payload
    held = []

    def delay(payload):
        held.append(payload)
        return PreviewPayload(1, 1, "", "delayed")

    monkeypatch.setattr(service, "build_payload", delay)
    for owner in ("attacker", "victim", "attacker"):
        controller.refresh_selected_file_preview(
            [],
            [owner + "-file"],
            1,
            1,
            gr.Request(username=owner, session_hash=owner + "-browser"),
        )
    for payload in reversed(held):
        result = build(replace(payload, file_name="", file_path=""))
        assert result.preview_src == ""
        assert "Selected file is unavailable" in result.preview_notice
    assert not any("access" in key or "request" in key for key in vars(controller))


def test_forged_source_and_client_path_do_not_grant_preview_access(url_controller):
    controller, storage = url_controller
    request = gr.Request(username="attacker", session_hash="attacker-browser")
    for callback, args in (
        (
            controller.on_selected_file_change,
            [[("mine", "victim-file")], ["victim-file"], {}],
        ),
        (
            controller.on_page_set,
            [1, "victim-file", str(storage / "victim-doc"), {}, 1],
        ),
    ):
        with pytest.raises(PreviewAccessError):
            callback(*args, request=request)


def test_displayed_stream_answer_cannot_replace_full_runtime_history():
    messages = [
        ("earlier file question", "earlier answer"),
        ("URL question", "final answer"),
    ]
    response = SimpleNamespace(answer="final answer", messages=messages)
    result = _with_displayed_final_answer(
        response,
        "stream display",
        preserved_history=[],
        chat_input="URL question",
    )
    assert result.messages is messages
    assert messages == [
        ("earlier file question", "earlier answer"),
        ("URL question", "final answer"),
    ]
    assert result.answer == "stream display"


def test_passive_url_preview_does_not_change_active_request_view(url_controller):
    from ktem.pages.chat.generation_store import get_current_view, set_current_view

    controller, _ = url_controller
    request = gr.Request(username="attacker", session_hash="pending-url")
    set_current_view(request.session_hash, "default_1")
    controller.refresh_selected_file_preview([], ["attacker-file"], 1, 1, request)
    assert get_current_view(request.session_hash) == "default_1"


def test_page_cache_receives_only_the_displayed_request_projection():
    from ktem.pages.chat.conversation_restore import cache_request_view
    from ktem.pages.chat.generation_store import get_view_revision

    request = gr.Request(username="owner", session_hash="page-projection")
    full = [("earlier document", "earlier answer"), ("URL question", "answer")]
    displayed = full[-1:]
    context = {
        "conversation_id": "conversation",
        "view_revision": get_view_revision(request.session_hash),
        "messages": full,
        "page_messages": displayed,
    }
    writer = Mock(return_value="cached")
    result = cache_request_view(writer)(
        "conversation",
        context,
        {},
        1,
        "URL question",
        "",
        "answer",
        "url",
        full,
        request,
    )
    assert result == "cached"
    assert writer.call_args.args[-1] is displayed
    assert context["messages"] is full
    context["page_messages"] = None
    assert (
        cache_request_view(writer)(
            "conversation", context, {}, 1, "q", "", "a", "url", full, request
        )
        == gr.skip()
    )
    assert writer.call_count == 1


def test_final_output_keeps_full_history_while_page_shows_its_own_turn():
    from ktem.pages.chat.chat_docqa_streaming import final_docqa_response_output

    from .test_chat_docqa_runtime_adapter import _FakeRuntimeDocQA

    response = _FakeRuntimeDocQA().run_turn(SimpleNamespace())
    response.messages.insert(0, ("another source", "earlier answer"))
    original = list(response.messages)
    page = SimpleNamespace(
        **{
            name: Mock(return_value="rendered")
            for name in (
                "_json_to_plot",
                "_generate_answer_panel_html",
                "_render_citations_card_html",
                "_render_reasoning_trace_html",
            )
        }
    )
    output = final_docqa_response_output(
        page,
        response=response,
        preserved_history=[],
        chat_input="What changed?",
        msg_placeholder="waiting",
        request_key="no-live-request",
        state_plot_panel=None,
        fallback_chat_state={},
        active_view=True,
        active_file_id="file-1",
        normalized_page_number=3,
    )
    assert len(output) == 14
    assert output[0] == [("What changed?", "runtime answer")]
    assert output[13] is response.messages
    assert output[13] == original
