from __future__ import annotations

import pytest
from ktem.pages.chat import chat_message_events
from ktem.pages.chat.chat_gradio_adapters import chat_submit_ports

from .event_chain_spy import EventGraphSpy, build_chat_page


def _fn_name(call):
    fn = call.params.get("fn")
    return getattr(fn, "name", getattr(fn, "__name__", None))


def _bind_submit(page, graph, monkeypatch, *, demo_mode: bool):
    monkeypatch.setattr(
        chat_message_events.gr,
        "on",
        lambda *args, **kwargs: graph.root("gr.on", "on", args, kwargs),
    )
    chat_message_events.bind_chat_submit_events(
        page,
        demo_mode=demo_mode,
        pdfview_js="pdf-js",
        scroll_answer_panel_js="scroll-js",
    )


def test_submit_ports_are_named_immutable_and_preserve_all_index_inputs():
    graph = EventGraphSpy()
    page = build_chat_page(graph, index_count=6)

    ports = chat_submit_ports(page)

    assert ports.submit.inputs == (
        page.chat_panel.text_input,
        page.chat_panel.chatbot,
        page._app.user_id,
        page._app.settings_state,
        page.chat_control.conversation_id,
        page.chat_control.conversation_rn,
        page.first_selector_choices,
        page._graph_source_ids,
        page._selected_page_text,
        page._selected_graph_context,
    )
    assert ports.submit.outputs == (
        page.chat_panel.text_input,
        page.chat_panel.chatbot,
        page.chat_control.conversation_id,
        page.chat_control.conversation,
        page.chat_control.conversation_rn,
        page._indices_input[0],
        page._indices_input[1],
        page._last_question,
        page._command_state,
        page._selected_page_text,
        page._selected_graph_context,
        page._graph_source_ids,
    )
    assert ports.runtime.inputs[-6:] == tuple(page._indices_input)
    assert len(ports.runtime.inputs) == 22 + len(page._indices_input)
    assert ports.runtime.outputs == (
        page.chat_panel.chatbot,
        page.info_panel,
        page.plot_panel,
        page.state_plot_panel,
        page.state_chat,
        page.answer_panel,
        page.citations_panel,
        page.reasoning_trace_panel,
        page._request_page_number,
        page._request_file_id,
        page._request_last_question,
        page._request_info_html,
        page._request_answer_html,
        page._request_chat_history,
    )
    assert ports.persist.inputs[-6:] == tuple(page._indices_input)
    assert ports.submit.inputs is ports.submit.inputs
    with pytest.raises((AttributeError, TypeError)):
        setattr(ports.submit, "inputs", (*ports.submit.inputs, object()))


def test_submit_chain_preserves_distinct_parent_nodes_and_exact_event_order(
    monkeypatch,
):
    graph = EventGraphSpy()
    page = build_chat_page(graph, index_count=5)

    _bind_submit(page, graph, monkeypatch, demo_mode=False)

    assert [call.verb for call in graph.calls] == [
        "on",
        "success",
        "success",
        "then",
        "then",
        "then",
        "success",
        "success",
        "then",
    ]
    assert [call.parent_id for call in graph.calls] == [
        None,
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
    ]
    assert len({call.node_id for call in graph.calls}) == len(graph.calls)
    assert [call.params.get("fn") for call in graph.calls] == [
        page.submit_msg,
        page.chat_fn,
        page.page_preview.cache_page_outputs,
        graph.calls[3].params["fn"],
        graph.calls[4].params["fn"],
        None,
        page.check_and_suggest_name_conv,
        page.chat_control.rename_conv,
        page.persist_data_source,
    ]
    assert graph.calls[6].params["inputs"] is page._request_chat_history
    assert graph.calls[7].params["outputs"] == [
        page.chat_control.conversation,
        page.chat_control.conversation,
        page.chat_control.conversation_rn,
    ]
    assert graph.calls[8].params["inputs"][-5:] == page._indices_input
    assert graph.calls[4].params["js"] == "pdf-js"
    assert graph.calls[5].params["js"] == "scroll-js"


def test_demo_submit_omits_only_persist_tail(monkeypatch):
    standard_graph = EventGraphSpy()
    standard_page = build_chat_page(standard_graph, index_count=4)
    _bind_submit(standard_page, standard_graph, monkeypatch, demo_mode=False)

    demo_graph = EventGraphSpy()
    demo_page = build_chat_page(demo_graph, index_count=4)
    _bind_submit(demo_page, demo_graph, monkeypatch, demo_mode=True)

    assert [call.verb for call in demo_graph.calls] == [
        call.verb for call in standard_graph.calls[:-1]
    ]
    assert [_fn_name(call) for call in demo_graph.calls] == [
        _fn_name(call) for call in standard_graph.calls[:-1]
    ]
