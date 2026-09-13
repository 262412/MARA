"""Regression expectations for passive restoration versus deliberate navigation."""

from types import SimpleNamespace
from unittest.mock import Mock

import gradio as gr
import pytest
from ktem.pages.chat import chat_conversation_events, chat_preview_events

from .event_chain_spy import ComponentSpy, EventGraphSpy, build_chat_page, linear_chain


@pytest.fixture(autouse=True)
def isolated_views(monkeypatch):
    from ktem.pages.chat import generation_store

    for name in (
        "GENERATION_CACHE",
        "ACTIVE_REQUESTS",
        "CURRENT_VIEW",
        "VIEW_REVISIONS",
    ):
        monkeypatch.setattr(generation_store, name, {})


def preview_graph():
    graph = EventGraphSpy()
    page = build_chat_page(graph)
    page._indices_input[1] = ComponentSpy(graph, "indices[1]")
    chat_preview_events.bind_chat_preview_events(
        page,
        demo_mode=False,
        recommended_papers_js="papers",
        pdfview_js="pdf",
        refresh_page_context_view=page.refresh_page_context_view,
    )
    return graph, page


def test_passive_source_update_cannot_clear_restored_history():
    graph, page = preview_graph()
    passive = next(call for call in graph.roots("indices[1]") if call.verb == "change")
    assert page.chat_panel.chatbot not in passive.params["outputs"]
    assert page.answer_panel not in passive.params["outputs"]


def test_only_user_page_number_input_restores_page_cache():
    graph, _ = preview_graph()
    assert [call.verb for call in graph.roots("chat_panel.page_number")] == ["input"]


def test_conversation_selection_resets_browser_page_cache():
    graph = EventGraphSpy()
    page = build_chat_page(graph)
    chat_conversation_events.bind_chat_conversation_events(
        page,
        demo_mode=False,
        chat_input_focus_js="focus",
        clear_bot_message_selection_js="clear",
        pdfview_js="pdf",
    )
    for trigger in ("chat_control.conversation", "chat_control.btn_new"):
        chain = linear_chain(graph, graph.roots(trigger)[0])
        selection = chain[0 if trigger == "chat_control.conversation" else 1]
        assert page._page_outputs_cache in selection.params["outputs"]


def test_restored_answer_includes_both_questions_and_answers():
    graph = EventGraphSpy()
    page = build_chat_page(graph)
    from ktem.pages.chat import ChatPage

    page._format_chat_message = ChatPage._format_chat_message.__get__(page)
    page._generate_answer_panel_html = ChatPage._generate_answer_panel_html.__get__(
        page
    )
    chat_conversation_events.bind_chat_conversation_events(
        page,
        demo_mode=False,
        chat_input_focus_js="focus",
        clear_bot_message_selection_js="clear",
        pdfview_js="pdf",
    )
    chain = linear_chain(graph, graph.roots("chat_control.conversation")[0])
    render = next(
        call.params["fn"]
        for call in chain
        if call.params.get("outputs") == [page.answer_panel]
    )
    html = render(
        [["first question", "first answer"], ["second question", "second answer"]]
    )
    assert all(
        value in html
        for value in (
            "first question",
            "first answer",
            "second question",
            "second answer",
        )
    )


def test_same_page_in_another_conversation_cannot_reuse_old_generation():
    from ktem.pages.chat.chat_docqa_streaming import prepare_chat_runtime_turn
    from ktem.pages.chat.generation_store import reset_view
    from ktem.pages.chat.page_preview_cache import get_cached_page_outputs

    request = gr.Request(username="owner", session_hash="browser")
    args = dict(
        chat_history=[("question", None)],
        selected_page_text="",
        active_file_id="file",
        page_number=1,
        request=request,
    )
    old = prepare_chat_runtime_turn(**args)
    assert old.is_active_view()
    reset_view("browser")
    cleared = ("cleared",) * 6
    assert (
        get_cached_page_outputs(
            {},
            1,
            "file",
            session_key="browser",
            clear_page_outputs=lambda: cleared,
            mindmap_placeholder="",
            answer_placeholder="",
        )
        == cleared
    )
    assert not old.is_active_view()
    new = prepare_chat_runtime_turn(**args)
    assert new.is_active_view()
    assert not old.is_active_view()


def test_late_authorized_selection_cannot_replace_newer_selection():
    from ktem.pages.chat.conversation_restore import restore_conversation

    request = gr.Request(username="owner", session_hash="browser")
    results = []

    def authorized_read(conversation_id, user_id, request):
        if conversation_id == "old":
            results.append(restore("new", user_id, request))
        return (conversation_id, [conversation_id])

    restore = restore_conversation(authorized_read)
    assert restore("old", "owner", request) == (gr.skip(),) * 3
    assert results == [("new", ["new"], {})]


def test_empty_or_denied_selection_clears_only_page_cache():
    from ktem.pages.chat.conversation_restore import restore_conversation

    original: tuple = ("", "", "", [], "other unchanged outputs")
    callback = Mock(return_value=original)
    request = gr.Request(username="other", session_hash="browser")
    result = restore_conversation(callback)("private", "forged", request)
    callback.assert_called_once_with("private", "forged", request)
    assert result == (*original, {})
    assert result[3] is original[3]


def test_late_preview_is_discarded_after_conversation_reset(monkeypatch):
    from ktem.pages.chat.generation_store import get_current_view, reset_view
    from ktem.pages.chat.page_preview import ChatPagePreviewController

    controller = ChatPagePreviewController(SimpleNamespace())
    request = gr.Request(username="owner", session_hash="browser")

    def resolve(*args, **kwargs):
        reset_view("browser")
        return "old", "old.txt", "/owned/old.txt"

    monkeypatch.setattr(controller, "resolve_pdf_source", resolve)
    monkeypatch.setattr(
        controller, "_build_preview_payload", lambda *args: (1, 1, "src", "")
    )
    assert (
        controller.on_selected_file_change([], ["old"], {}, request)
        == (gr.skip(),) * 14
    )
    assert get_current_view("browser") == ""


def test_late_stream_cache_cannot_contaminate_reset_conversation():
    from ktem.pages.chat.conversation_restore import cache_request_view
    from ktem.pages.chat.generation_store import reset_view

    writer = Mock()
    request = gr.Request(username="owner", session_hash="browser")
    context = {"conversation_id": "same-id", "view_revision": 0}
    reset_view("browser")
    assert (
        cache_request_view(writer)(
            "same-id", context, {}, 1, "q", "", "a", "file", [], request
        )
        == gr.skip()
    )
    writer.assert_not_called()
