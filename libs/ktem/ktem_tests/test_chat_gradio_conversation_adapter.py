from __future__ import annotations

from typing import cast

import ktem.pages.chat as chat_page_module
from ktem.pages.chat import ChatPage, chat_conversation_events
from ktem.pages.chat.chat_gradio_adapters import (
    chat_app_load_ports,
    chat_conversation_ports,
)

from .event_chain_spy import EventGraphSpy, build_chat_page, linear_chain, marker


def _bind_conversation(page, *, demo_mode: bool):
    chat_conversation_events.bind_chat_conversation_events(
        page,
        demo_mode=demo_mode,
        chat_input_focus_js="focus-js",
        clear_bot_message_selection_js="clear-selection-js",
        pdfview_js="pdf-js",
    )


def _fn_name(call):
    fn = call.params.get("fn")
    return getattr(fn, "name", getattr(fn, "__name__", None))


def test_conversation_ports_preserve_fixed_outputs_and_every_index_component():
    page = build_chat_page(EventGraphSpy(), index_count=7)

    ports = chat_conversation_ports(page, demo_mode=False)

    assert ports.selection.outputs == (
        page.chat_control.conversation_id,
        page.chat_control.conversation,
        page.chat_control.conversation_rn,
        page.chat_panel.chatbot,
        page.followup_questions,
        page.info_panel,
        page.state_plot_panel,
        page.state_retrieval_history,
        page.state_plot_history,
        page.chat_control.cb_is_public,
        page.state_chat,
        *page._indices_input,
    )
    assert ports.preview.inputs == (
        page.first_selector_choices,
        page._indices_input[1],
        page.chat_panel.page_number,
        page._active_file_total_pages,
    )
    assert len(ports.preview.outputs) == 7
    assert len(ports.context.outputs) == 3
    assert ports.suggestions.inputs == (
        page._app.settings_state,
        page.language,
        page.chat_panel.chatbot,
        page._use_suggestion,
    )


def test_standard_conversation_registration_and_select_tail_are_exact():
    graph = EventGraphSpy()
    page = build_chat_page(graph, index_count=6)

    _bind_conversation(page, demo_mode=False)

    assert [root.trigger for root in graph.roots()] == [
        "chat_control.btn_chat_expand",
        "chat_control.btn_new",
        "chat_control.btn_del",
        "chat_control.btn_del_conf",
        "chat_control.btn_del_cnl",
        "chat_control.btn_conversation_rn",
        "chat_control.conversation_rn",
        "chat_control.conversation",
    ]
    new_chain = linear_chain(graph, graph.roots("chat_control.btn_new")[0])
    assert [_fn_name(call) for call in new_chain] == [
        "chat_control.new_conv",
        "chat_control.select_conv",
        "page._json_to_plot",
        "<lambda>",
        "page.render_latest_citations_card",
        "page.render_latest_reasoning_trace",
        "<lambda>",
        "page.suggest_chat_conv",
        None,
    ]
    assert new_chain[0].params["inputs"] is page._app.user_id
    assert new_chain[1].params["outputs"][-6:] == page._indices_input
    delete_chain = linear_chain(graph, graph.roots("chat_control.btn_del_conf")[0])
    assert [_fn_name(call) for call in delete_chain] == [
        "chat_control.delete_conv",
        "chat_control.select_conv",
        "page._json_to_plot",
        "page.render_latest_citations_card",
        "page.render_latest_reasoning_trace",
        "<lambda>",
    ]
    rename = graph.roots("chat_control.conversation_rn")[0]
    assert _fn_name(rename) == "chat_control.rename_conv"
    assert rename.params["outputs"] == [
        page.chat_control.conversation,
        page.chat_control.conversation,
        page.chat_control.conversation_rn,
    ]
    select_root = graph.roots("chat_control.conversation")[0]
    select_chain = linear_chain(graph, select_root)
    assert [_fn_name(call) for call in select_chain] == [
        "chat_control.select_conv",
        "page._json_to_plot",
        "<lambda>",
        "page.suggest_chat_conv",
        "page_preview.refresh_selected_file_preview",
        "page.refresh_page_context_view",
        "<lambda>",
        "<lambda>",
        "<lambda>",
        "<lambda>",
        "<lambda>",
        "page.render_latest_citations_card",
        "page.render_latest_reasoning_trace",
        None,
    ]
    assert [call.parent_id for call in select_chain[1:]] == [
        call.node_id for call in select_chain[:-1]
    ]
    assert select_chain[6].params["js"] == "clear-selection-js"
    assert select_chain[8].params["js"] == "pdf-js"
    assert select_chain[-1].params["js"] == "focus-js"
    assert select_chain[0].params["outputs"][-6:] == page._indices_input


def test_standard_conversation_registration_does_not_require_demo_paper_list():
    graph = EventGraphSpy()
    page = build_chat_page(graph)
    del page.paper_list

    _bind_conversation(page, demo_mode=False)

    assert graph.roots("chat_control.btn_new")


def test_demo_conversation_adds_only_visibility_branch_and_keeps_root_order():
    graph = EventGraphSpy()
    page = build_chat_page(graph, index_count=5)

    _bind_conversation(page, demo_mode=True)

    assert [root.trigger for root in graph.roots()] == [
        "chat_control.btn_chat_expand",
        "chat_control.btn_demo_logout",
        "chat_control.btn_new",
        "chat_control.conversation",
    ]
    select_chain = linear_chain(graph, graph.roots("chat_control.conversation")[0])
    assert len(select_chain) == 15
    assert _fn_name(select_chain[4]) == "<lambda>"
    assert select_chain[4].params["outputs"] == [
        page.paper_list.accordion,
        page.chat_settings,
    ]
    assert _fn_name(select_chain[5]) == "page_preview.refresh_selected_file_preview"
    new_chain = linear_chain(graph, graph.roots("chat_control.btn_new")[0])
    assert [_fn_name(call) for call in new_chain] == [
        "chat_control.clear_conv",
        "<lambda>",
        "<lambda>",
        "page.render_latest_citations_card",
        "page.render_latest_reasoning_trace",
        "<lambda>",
        "page.suggest_chat_conv",
        None,
    ]
    assert new_chain[0].params["outputs"][-5:] == page._indices_input
    assert new_chain[-1].params["js"] == "focus-js"


def test_sign_out_uses_named_conversation_outputs_and_clear_adapter():
    graph = EventGraphSpy()
    page = build_chat_page(graph, index_count=6)
    subscriptions = []
    clear_calls = []
    page.knowledge_graph = False
    page.file_index = None

    def clear_conv():
        clear_calls.append(True)
        return "signed-out"

    page.chat_control.clear_conv = clear_conv
    page._app.subscribe_event = lambda **definition: subscriptions.append(definition)

    ChatPage.on_subscribe_public_events(cast(ChatPage, page))

    assert [item["name"] for item in subscriptions] == ["onSignIn", "onSignOut"]
    sign_out = subscriptions[1]["definition"]
    assert sign_out["outputs"] == list(
        chat_conversation_ports(page, demo_mode=False).selection.outputs
    )
    assert sign_out["fn"]() == "signed-out"
    assert clear_calls == [True]
    assert sign_out["show_progress"] == "hidden"


def test_demo_app_load_chain_uses_named_ports_and_exact_parent_order(monkeypatch):
    graph = EventGraphSpy()
    page = build_chat_page(graph, index_count=4)
    page.chat_control.toggle_demo_login_visibility = marker(
        "chat_control.toggle_demo_login_visibility"
    )
    page.chat_control.cb_suggest_chat = marker("chat_control.cb_suggest_chat")
    page.chat_control.btn_demo_login = marker("chat_control.btn_demo_login")
    monkeypatch.setattr(chat_page_module, "KH_DEMO_MODE", True)

    ChatPage._on_app_created(cast(ChatPage, page))

    chain = linear_chain(graph, graph.roots("app.load")[0])
    ports = chat_app_load_ports(page)
    assert [_fn_name(call) for call in chain] == [
        "<lambda>",
        "chat_control.toggle_demo_login_visibility",
        "page.suggest_chat_conv",
        None,
    ]
    assert chain[0].params["inputs"] == list(ports.api_key.inputs)
    assert chain[1].params["outputs"] == list(ports.login_visibility.outputs)
    assert chain[2].params["inputs"] == list(ports.suggestions.inputs)
    assert chain[-1].params["js"] == chat_page_module.chat_input_focus_js
