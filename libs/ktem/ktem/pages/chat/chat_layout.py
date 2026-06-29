from __future__ import annotations

from typing import Any

import gradio as gr
from ktem.index.file.ui import File

from kotaemon.indices.ingests.files import KH_DEFAULT_FILE_EXTRACTORS

from .chat_docqa_runtime import render_docqa_runtime_controls
from .chat_panel import ChatPanel
from .chat_suggestion import ChatSuggestion
from .common import STATE
from .control import ConversationControl
from .demo_hint import HintPage
from .paper_list import PaperListPage
from .report import ReportIssue
from .studio_artifact_control_rendering import render_studio_artifact_controls
from .studio_artifacts import render_notebook_panel_html


def render_chat_workbench_layout(
    page: Any,
    *,
    demo_mode: bool,
    reasoning_limits: int,
    default_setting: str,
    info_panel_scales: dict[bool, int],
) -> None:
    with gr.Row(elem_id="page-workbench-layout"):
        render_workbench_states(page)
        render_corpus_panel(page, demo_mode=demo_mode)
        render_reader_panel(
            page,
            demo_mode=demo_mode,
            reasoning_limits=reasoning_limits,
            default_setting=default_setting,
        )
        render_answer_panel(page, info_panel_scales=info_panel_scales)

    page.followup_questions = page.chat_suggestion.examples
    page.followup_questions_ui = page.chat_suggestion.accordion


def render_workbench_states(page: Any) -> None:
    page.state_chat = gr.State(STATE)
    page.state_retrieval_history = gr.State([])
    page.state_plot_history = gr.State([])
    page.state_plot_panel = gr.State(None)
    page._graph_source_ids = gr.State([])
    page.first_selector_choices = gr.State(None)
    page._selected_page_text = gr.Textbox(
        value="", visible=False, elem_id="selected-page-text"
    )
    page._selected_graph_context = gr.Textbox(
        value="", visible=False, elem_id="selected-graph-context"
    )
    page._chat_file_click = gr.Textbox(
        value="", visible=False, elem_id="chat-file-click"
    )


def render_corpus_panel(page: Any, *, demo_mode: bool) -> None:
    with gr.Column(scale=1, elem_id="conv-settings-panel") as page.conv_column:
        gr.HTML(_corpus_header_html())
        page.upload_scope_hint = gr.Markdown("", elem_id="chat-upload-hint")

        if len(page._app.index_manager.indices) > 0:
            page.quick_file_upload_status = gr.Markdown(
                elem_id="quick-file-upload-status"
            )
            render_corpus_add_panel(page, demo_mode=demo_mode)

        render_chat_file_browser(page)
        render_advanced_source_selectors(page, demo_mode=demo_mode)
        page.chat_suggestion = ChatSuggestion(page._app, show_panel=False)
        render_optional_demo_sidebar(page, demo_mode=demo_mode)


def render_corpus_add_panel(page: Any, *, demo_mode: bool) -> None:
    with gr.Column(elem_id="corpus-add-panel"):
        if not demo_mode:
            page.quick_file_upload = File(
                file_types=list(KH_DEFAULT_FILE_EXTRACTORS.keys()),
                file_count="multiple",
                container=True,
                show_label=False,
                elem_id="quick-file",
            )
        page.quick_urls = gr.Textbox(
            placeholder=(
                "Paste URLs"
                if not demo_mode
                else "Paste Arxiv URLs\n(https://arxiv.org/abs/xxx)"
            ),
            lines=1,
            container=False,
            show_label=False,
            elem_id="quick-url" if not demo_mode else "quick-url-demo",
        )


def render_chat_file_browser(page: Any) -> None:
    with gr.Column(elem_id="chat-file-browser"):
        page.chat_file_filter = gr.Textbox(
            value="",
            label="Search files",
            placeholder="Search files...",
            elem_id="chat-file-filter",
            container=False,
            show_label=False,
            visible=True,
        )
        page.chat_file_rows = gr.State([])
        page.chat_selected_file = gr.Markdown(
            "Focus: all files",
            elem_id="chat-selected-file",
        )
        page.chat_file_list = gr.HTML(
            "<div class='chat-file-empty'>No files uploaded</div>",
            elem_id="chat-file-list",
        )
        page.workbench_file_summary = gr.HTML(
            page._render_corpus_summary_html([]),
            elem_id="workbench-file-summary",
        )


def render_advanced_source_selectors(page: Any, *, demo_mode: bool) -> None:
    with gr.Accordion(
        label="Advanced Source Selectors",
        open=False,
        elem_id="advanced-source-selectors",
        visible=False,
    ):
        for index_id, index in enumerate(page._app.index_manager.indices):
            _render_index_selector(page, index_id, index, demo_mode=demo_mode)


def render_optional_demo_sidebar(page: Any, *, demo_mode: bool) -> None:
    if not demo_mode:
        page.report_issue = ReportIssue(page._app, show_panel=False)
        return

    with gr.Accordion(label="Related papers", open=False):
        page.related_papers = gr.Markdown(elem_id="related-papers")
    page.hint_page = HintPage(page._app)


def render_reader_panel(
    page: Any,
    *,
    demo_mode: bool,
    reasoning_limits: int,
    default_setting: str,
) -> None:
    with gr.Column(scale=6, elem_id="chat-area"):
        if demo_mode:
            page.paper_list = PaperListPage(page._app)

        with gr.Row(elem_id="reader-workbench"):
            render_page_strip_panel(page)
            render_document_reader_panel(
                page,
                reasoning_limits=reasoning_limits,
                default_setting=default_setting,
            )


def render_page_strip_panel(page: Any) -> None:
    with gr.Column(scale=1, elem_id="page-strip-panel"):
        page.page_strip_file_summary = gr.HTML(
            page._render_page_strip_header("", "", "", 1),
            elem_id="page-strip-file-summary",
        )
        page.page_strip_search = gr.State(value="")
        page.page_thumbnail_strip = gr.HTML(
            page._render_page_thumbnail_strip("", "", "", 1, 1),
            elem_id="page-thumbnail-list",
        )


def render_document_reader_panel(
    page: Any, *, reasoning_limits: int, default_setting: str
) -> None:
    with gr.Column(scale=4, elem_id="document-reader-panel"):
        gr.HTML(_reader_toolbar_html(), elem_id="reader-toolbar")
        with gr.Column(elem_id="chat-preview-section"):
            page.chat_panel = ChatPanel(page._app)

        page.chat_panel.render_notice_and_pager()
        page.page_metadata_strip = gr.HTML(
            page._render_page_metadata_strip("", "", "", 1, 1),
            elem_id="page-metadata-strip",
        )
        render_docqa_runtime_controls(
            page,
            reasoning_limits=reasoning_limits,
            default_setting=default_setting,
        )


def render_answer_panel(page: Any, *, info_panel_scales: dict[bool, int]) -> None:
    with gr.Column(
        scale=info_panel_scales[False], elem_id="chat-info-panel"
    ) as page.info_column:
        with gr.Column(elem_id="answer-expand"):
            gr.HTML(_ask_tabs_html())
            page.chat_panel.render_input()
            page.kg_answer_hint = gr.HTML(
                value=_empty_kg_answer_hint_html(),
                elem_id="kg-answer-hint",
            )
            gr.HTML("<div class='answer-panel-label'>Answer</div>")
            page.answer_panel = gr.HTML(value="", elem_id="answer-panel")
            page.citations_panel = gr.HTML(
                page._render_citations_card_html(),
                elem_id="citations-card",
            )
            page.reasoning_trace_panel = gr.HTML(
                page._render_reasoning_trace_html(),
                elem_id="reasoning-trace-card",
            )
            page.notebook_panel = gr.HTML(
                render_notebook_panel_html(), elem_id="notebook-panel-card"
            )
            render_studio_artifact_controls(page)

        with gr.Column(elem_id="info-expand"):
            page.plot_panel = gr.HTML("", visible=False)
            page.info_panel = gr.HTML(elem_id="html-info-panel")

        render_conversation_dock(page)


def render_conversation_dock(page: Any) -> None:
    with gr.Accordion(label="Conversation", open=False, elem_id="conversation-dock"):
        page.chat_control = ConversationControl(page._app)


def _render_index_selector(
    page: Any, index_id: int, index: Any, *, demo_mode: bool
) -> None:
    index.selector = None
    index_ui = index.get_selector_component_ui()
    if not index_ui:
        return

    index_ui.unrender()
    is_first_index = index_id == 0
    index_name = index.name
    if demo_mode and is_first_index:
        index_name = "Select from Paper Collection"

    with gr.Accordion(
        label=index_name, open=is_first_index, elem_id=f"index-{index_id}"
    ):
        index_ui.render()
        gr_index = index_ui.as_gradio_component()
        if index_id == 0:
            page.first_selector_choices = index_ui.selector_choices
            page.first_indexing_file_fn = None
            page.first_indexing_url_fn = None
        _record_index_selector(page, index, index_ui, gr_index)
    setattr(page, f"_index_{index.id}", index_ui)


def _record_index_selector(page: Any, index: Any, index_ui: Any, gr_index: Any) -> None:
    if not gr_index:
        return
    if isinstance(gr_index, list):
        index.selector = tuple(
            range(len(page._indices_input), len(page._indices_input) + len(gr_index))
        )
        index.default_selector = index_ui.default()
        page._indices_input.extend(gr_index)
        return
    index.selector = len(page._indices_input)
    index.default_selector = index_ui.default()
    page._indices_input.append(gr_index)


def _corpus_header_html() -> str:
    return (
        "<div class='corpus-pane-title'>"
        "<h2>Corpus</h2>"
        "<button type='button' id='corpus-add-trigger'>+ Add</button>"
        "</div>"
    )


def _reader_toolbar_html() -> str:
    return (
        "<div class='reader-toolbar'>"
        "<div class='reader-toolbar__tools'>"
        "<button type='button' aria-label='Zoom out' data-reader-action='zoom-out'>-</button>"
        "<strong id='reader-zoom-label' class='reader-toolbar__zoom'>100%</strong>"
        "<button type='button' aria-label='Zoom in' data-reader-action='zoom-in'>+</button>"
        "</div>"
        "<div class='reader-toolbar__tools'>"
        "<button type='button' aria-label='Download preview' data-reader-action='download'>"
        "<svg viewBox='0 0 24 24'><path d='M12 3v12m0 0 4-4m-4 4-4-4M5 21h14'/></svg>"
        "</button>"
        "<button type='button' aria-label='More reader options' aria-expanded='false' data-reader-action='more'>...</button>"
        "</div>"
        "</div>"
    )


def _ask_tabs_html() -> str:
    return (
        "<div class='right-ask-tabs'>"
        "<button type='button' class='is-active'>Ask this page</button>"
        "<button type='button'>Notes</button>"
        "</div>"
    )


def _empty_kg_answer_hint_html() -> str:
    return (
        "<div class='kg-answer-hint kg-answer-hint--empty'>"
        "Select a node in the knowledge graph mind map to pin "
        "context and get a suggested question."
        "</div>"
    )
