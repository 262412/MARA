from __future__ import annotations

from ktem.pages.chat import chat_preview_events
from ktem.pages.chat.chat_gradio_adapters import chat_preview_ports

from .event_chain_spy import (
    ComponentSpy,
    EventGraphSpy,
    build_chat_page,
    linear_chain,
)


def _fn_name(call):
    fn = call.params.get("fn")
    return getattr(fn, "name", getattr(fn, "__name__", None))


def _preview_page(graph):
    page = build_chat_page(graph, index_count=5)
    page._indices_input[1] = ComponentSpy(graph, "indices[1]")
    return page


def test_preview_ports_preserve_exact_selected_navigation_timer_and_context_abi():
    page = _preview_page(EventGraphSpy())

    ports = chat_preview_ports(page)

    assert ports.selected_file.inputs == (
        page.first_selector_choices,
        page._indices_input[1],
        page._page_outputs_cache,
    )
    assert ports.selected_file.outputs == (
        page._active_file_id,
        page._active_file_name,
        page._active_file_path,
        page.chat_panel.page_number,
        page._active_file_total_pages,
        page.chat_panel.pdf_preview_src,
        page.chat_panel.pdf_preview_notice,
        page._last_question,
        page.info_panel,
        page.plot_panel,
        page.state_plot_panel,
        page.answer_panel,
        page.chat_panel.chatbot,
        page._page_outputs_cache,
    )
    assert len(ports.navigation.inputs) == 5
    assert len(ports.navigation.outputs) == 10
    assert len(ports.timer.inputs) == 7
    assert ports.timer.outputs == (
        page.chat_panel.page_number,
        page._active_file_total_pages,
        page.chat_panel.pdf_preview_src,
        page.chat_panel.pdf_preview_notice,
    )
    assert len(ports.context.inputs) == 6
    assert len(ports.context.outputs) == 3
    assert len(ports.conversation_preview.inputs) == 4
    assert len(ports.conversation_preview.outputs) == 7


def test_preview_bindings_keep_root_order_and_distinct_context_tail_parents():
    graph = EventGraphSpy()
    page = _preview_page(graph)

    chat_preview_events.bind_chat_preview_events(
        page,
        demo_mode=False,
        recommended_papers_js="papers-js",
        pdfview_js="pdf-js",
        refresh_page_context_view=page.refresh_page_context_view,
    )

    assert [root.trigger for root in graph.roots()] == [
        "indices[1]",
        "chat_panel.preview_refresh_timer",
        "chat_panel.prev_page_btn",
        "chat_panel.next_page_btn",
        "chat_panel.page_number",
    ]
    expected_handlers = {
        "indices[1]": "page_preview.on_selected_file_change",
        "chat_panel.prev_page_btn": "page_preview.on_prev_page",
        "chat_panel.next_page_btn": "page_preview.on_next_page",
        "chat_panel.page_number": "page_preview.on_page_set",
    }
    for trigger, handler in expected_handlers.items():
        chain = linear_chain(graph, graph.roots(trigger)[0])
        assert [_fn_name(call) for call in chain] == [
            handler,
            "<lambda>",
            "page.refresh_page_context_view",
            "<lambda>",
        ]
        assert [call.parent_id for call in chain[1:]] == [
            call.node_id for call in chain[:-1]
        ]
        assert chain[-1].params["js"] == "pdf-js"


def test_preview_timer_has_no_context_or_thumbnail_refresh_tail():
    graph = EventGraphSpy()
    page = _preview_page(graph)

    chat_preview_events.bind_preview_refresh_timer(page)

    timer = graph.roots("chat_panel.preview_refresh_timer")[0]
    assert _fn_name(timer) == "page_preview.on_preview_tick"
    assert timer.params["inputs"] == list(chat_preview_ports(page).timer.inputs)
    assert timer.params["outputs"] == list(chat_preview_ports(page).timer.outputs)
    assert linear_chain(graph, timer) == [timer]
