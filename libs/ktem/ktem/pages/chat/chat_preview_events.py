from __future__ import annotations

from typing import Any, Callable

from .chat_gradio_adapters import ChatPreviewPorts, chat_preview_ports


def bind_chat_preview_events(
    page: Any,
    *,
    demo_mode: bool,
    recommended_papers_js: str,
    pdfview_js: str,
    refresh_page_context_view: Callable[..., Any],
) -> None:
    bind_recommended_paper_events(page, demo_mode, recommended_papers_js)
    bind_selected_file_change_event(page, pdfview_js, refresh_page_context_view)
    bind_preview_refresh_timer(page)
    bind_preview_page_button(
        page,
        button=page.chat_panel.prev_page_btn,
        handler=page.page_preview.on_prev_page,
        pdfview_js=pdfview_js,
        refresh_page_context_view=refresh_page_context_view,
    )
    bind_preview_page_button(
        page,
        button=page.chat_panel.next_page_btn,
        handler=page.page_preview.on_next_page,
        pdfview_js=pdfview_js,
        refresh_page_context_view=refresh_page_context_view,
    )
    bind_page_number_change_event(page, pdfview_js, refresh_page_context_view)


def bind_recommended_paper_events(
    page: Any,
    demo_mode: bool,
    recommended_papers_js: str,
) -> None:
    if demo_mode and len(page._indices_input) > 0:
        page._indices_input[1].change(
            page.get_recommendations,
            inputs=[page.first_selector_choices, page._indices_input[1]],
            outputs=[page.related_papers],
        ).then(
            fn=None,
            inputs=None,
            outputs=None,
            js=recommended_papers_js,
        )


def bind_selected_file_change_event(
    page: Any,
    pdfview_js: str,
    refresh_page_context_view: Callable[..., Any],
) -> None:
    if len(page._indices_input) <= 1:
        return

    ports = chat_preview_ports(page)
    event_chain = page._indices_input[1].change(
        fn=page.page_preview.on_selected_file_change,
        inputs=ports.selected_file.gradio_inputs,
        outputs=ports.selected_file.gradio_outputs,
        show_progress="hidden",
    )
    _append_context_refresh(
        event_chain, page, ports, pdfview_js, refresh_page_context_view
    )


def bind_preview_refresh_timer(page: Any) -> None:
    ports = chat_preview_ports(page)
    page.chat_panel.preview_refresh_timer.tick(
        fn=page.page_preview.on_preview_tick,
        inputs=ports.timer.gradio_inputs,
        outputs=ports.timer.gradio_outputs,
        show_progress="hidden",
    )


def bind_preview_page_button(
    page: Any,
    *,
    button: Any,
    handler: Callable[..., Any],
    pdfview_js: str,
    refresh_page_context_view: Callable[..., Any],
) -> None:
    ports = chat_preview_ports(page)
    event_chain = button.click(
        fn=handler,
        inputs=ports.navigation.gradio_inputs,
        outputs=ports.navigation.gradio_outputs,
        show_progress="hidden",
    )
    _append_context_refresh(
        event_chain, page, ports, pdfview_js, refresh_page_context_view
    )


def bind_page_number_change_event(
    page: Any,
    pdfview_js: str,
    refresh_page_context_view: Callable[..., Any],
) -> None:
    ports = chat_preview_ports(page)
    event_chain = page.chat_panel.page_number.change(
        fn=page.page_preview.on_page_set,
        inputs=ports.navigation.gradio_inputs,
        outputs=ports.navigation.gradio_outputs,
        show_progress="hidden",
    )
    _append_context_refresh(
        event_chain, page, ports, pdfview_js, refresh_page_context_view
    )


def _append_context_refresh(
    event_chain: Any,
    page: Any,
    ports: ChatPreviewPorts,
    pdfview_js: str,
    refresh_page_context_view: Callable[..., Any],
) -> Any:
    return (
        event_chain.then(
            fn=lambda: "",
            outputs=ports.clear_selection.gradio_outputs,
            show_progress="hidden",
        )
        .then(
            fn=refresh_page_context_view,
            inputs=ports.context.gradio_inputs,
            outputs=ports.context.gradio_outputs,
            show_progress="hidden",
        )
        .then(
            fn=lambda: True,
            inputs=None,
            outputs=ports.pdf_refresh.gradio_outputs,
            js=pdfview_js,
        )
    )
