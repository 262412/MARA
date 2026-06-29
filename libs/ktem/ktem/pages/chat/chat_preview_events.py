from __future__ import annotations

from typing import Any, Callable


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

    event_chain = page._indices_input[1].change(
        fn=page.page_preview.on_selected_file_change,
        inputs=[
            page.first_selector_choices,
            page._indices_input[1],
            page._page_outputs_cache,
        ],
        outputs=_selected_file_outputs(page),
        show_progress="hidden",
    )
    _append_context_refresh(event_chain, page, pdfview_js, refresh_page_context_view)


def bind_preview_refresh_timer(page: Any) -> None:
    page.chat_panel.preview_refresh_timer.tick(
        fn=page.page_preview.on_preview_tick,
        inputs=[
            page._active_file_id,
            page._active_file_name,
            page._active_file_path,
            page.chat_panel.page_number,
            page._active_file_total_pages,
            page.chat_panel.pdf_preview_src,
            page.chat_panel.pdf_preview_notice,
        ],
        outputs=[
            page.chat_panel.page_number,
            page._active_file_total_pages,
            page.chat_panel.pdf_preview_src,
            page.chat_panel.pdf_preview_notice,
        ],
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
    event_chain = button.click(
        fn=handler,
        inputs=_page_navigation_inputs(page),
        outputs=_page_navigation_outputs(page),
        show_progress="hidden",
    )
    _append_context_refresh(event_chain, page, pdfview_js, refresh_page_context_view)


def bind_page_number_change_event(
    page: Any,
    pdfview_js: str,
    refresh_page_context_view: Callable[..., Any],
) -> None:
    event_chain = page.chat_panel.page_number.change(
        fn=page.page_preview.on_page_set,
        inputs=_page_navigation_inputs(page),
        outputs=_page_navigation_outputs(page),
        show_progress="hidden",
    )
    _append_context_refresh(event_chain, page, pdfview_js, refresh_page_context_view)


def _append_context_refresh(
    event_chain: Any,
    page: Any,
    pdfview_js: str,
    refresh_page_context_view: Callable[..., Any],
) -> Any:
    return (
        event_chain.then(
            fn=lambda: "",
            outputs=[page._selected_page_text],
            show_progress="hidden",
        )
        .then(
            fn=refresh_page_context_view,
            inputs=_page_context_inputs(page),
            outputs=[
                page.page_strip_file_summary,
                page.page_thumbnail_strip,
                page.page_metadata_strip,
            ],
            show_progress="hidden",
        )
        .then(
            fn=lambda: True,
            inputs=None,
            outputs=[page._preview_links],
            js=pdfview_js,
        )
    )


def _selected_file_outputs(page: Any) -> list[Any]:
    return [
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
    ]


def _page_navigation_inputs(page: Any) -> list[Any]:
    return [
        page.chat_panel.page_number,
        page._active_file_id,
        page._active_file_path,
        page._page_outputs_cache,
        page._active_file_total_pages,
    ]


def _page_navigation_outputs(page: Any) -> list[Any]:
    return [
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
    ]


def _page_context_inputs(page: Any) -> list[Any]:
    return [
        page._active_file_id,
        page._active_file_name,
        page._active_file_path,
        page.chat_panel.page_number,
        page._active_file_total_pages,
        page.page_strip_search,
    ]
