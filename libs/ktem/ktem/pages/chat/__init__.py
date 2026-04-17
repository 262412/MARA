import asyncio
import html
import json
import logging
import os
import re
from copy import deepcopy
from typing import Optional

import gradio as gr
from decouple import config
from ktem.app import BasePage
from ktem.components import reasonings
from ktem.db.models import Conversation, engine
from ktem.index.file.ui import File
from ktem.reasoning.prompt_optimization.mindmap import MINDMAP_HTML_EXPORT_TEMPLATE
from ktem.reasoning.prompt_optimization.suggest_conversation_name import (
    SuggestConvNamePipeline,
)
from ktem.reasoning.prompt_optimization.suggest_followup_chat import (
    SuggestFollowupQuesPipeline,
)
from plotly.io import from_json
from pypdf import PdfReader
from sqlmodel import Session, select
from theflow.settings import settings as flowsettings
from theflow.utils.modules import import_dotted_string

from kotaemon.base import Document
from kotaemon.indices.ingests.files import KH_DEFAULT_FILE_EXTRACTORS
from kotaemon.indices.qa.utils import strip_think_tag

from ...utils import SUPPORTED_LANGUAGE_MAP, get_file_names_regex, get_urls
from ...utils.commands import WEB_SEARCH_COMMAND
from ...utils.hf_papers import get_recommended_papers
from ...utils.rate_limit import check_rate_limit
from .chat_panel import ChatPanel
from .generation_store import (
    get_current_view,
    init_cache_entry,
    make_page_key,
    make_request_key,
    mark_done,
    mark_error,
    set_current_view,
    update_answer,
    update_mindmap,
    update_plot,
    update_reasoning_state,
)
from .knowledge_graph_service import GlobalKnowledgeGraphService
from .page_preview import ChatPagePreviewController
from .chat_suggestion import ChatSuggestion
from .common import STATE
from .control import ConversationControl
from .demo_hint import HintPage
from .paper_list import PaperListPage
from .report import ReportIssue

KH_DEMO_MODE = getattr(flowsettings, "KH_DEMO_MODE", False)
KH_SSO_ENABLED = getattr(flowsettings, "KH_SSO_ENABLED", False)
KH_WEB_SEARCH_BACKEND = getattr(flowsettings, "KH_WEB_SEARCH_BACKEND", None)
logger = logging.getLogger(__name__)
WebSearch = None
if KH_WEB_SEARCH_BACKEND:
    try:
        WebSearch = import_dotted_string(KH_WEB_SEARCH_BACKEND, safe=False)
    except (ImportError, AttributeError) as e:
        logger.warning("Error importing %s: %s", KH_WEB_SEARCH_BACKEND, e)

# Maximum number of reasoning iterations allowed (limited in demo mode)
REASONING_LIMITS = 2 if KH_DEMO_MODE else 10
DEFAULT_SETTING = "(default)"
# Scale factors for info panel expansion (expanded: 8, collapsed: 4)
INFO_PANEL_SCALES = {True: 8, False: 4}
# Default question for document summarization
DEFAULT_QUESTION = (
    "What is the summary of this document?"
    if not KH_DEMO_MODE
    else "What is the summary of this paper?"
)

# JavaScript to focus chat input after actions
chat_input_focus_js = """
function() {
    let chatInput = document.querySelector("#chat-input textarea");
    chatInput.focus();
}
"""

# JavaScript to submit URL input by simulating Enter key press
quick_urls_submit_js = """
function() {
    let urlInput = document.querySelector("#quick-url-demo textarea");
    urlInput.dispatchEvent(new KeyboardEvent('keypress', {'key': 'Enter'}));
}
"""

# JavaScript to handle recommended paper clicks and auto-submit URLs
recommended_papers_js = """
function() {
    // Get all links and attach click event
    var links = document.querySelectorAll("#related-papers a");

    function submitPaper(event) {
        event.preventDefault();
        var target = event.currentTarget;
        var url = target.getAttribute("href");

        let newChatButton = document.querySelector("#new-conv-button");
        newChatButton.click();

        setTimeout(() => {
            let urlInput = document.querySelector("#quick-url-demo textarea");
            // Fill the URL input
            urlInput.value = url;
            urlInput.dispatchEvent(new Event("input", { bubbles: true }));
            urlInput.dispatchEvent(new KeyboardEvent('keypress', {'key': 'Enter'}));
            }, 500
        );
    }

    for (var i = 0; i < links.length; i++) {
        links[i].onclick = submitPaper;
    }
}
"""

# JavaScript to clear text selection highlighting from bot messages
clear_bot_message_selection_js = """
function() {
    var bot_messages = document.querySelectorAll(
        "div#main-chat-bot div.message-row.bot-row"
    );
    bot_messages.forEach(message => {
        message.classList.remove("text_selection");
    });
}
"""

pdfview_js = """
function() {
    setTimeout(fullTextSearch(), 100);

    // Get all links and attach click event
    var links = document.getElementsByClassName("pdf-link");
    for (var i = 0; i < links.length; i++) {
        links[i].onclick = openModal;
    }

    // Get all citation links and attach click event
    var links = document.querySelectorAll("a.citation");
    for (var i = 0; i < links.length; i++) {
        links[i].onclick = scrollToCitation;
    }

    var markmap_div = document.querySelector("div.markmap");
    var mindmap_el_script = document.querySelector('div.markmap script');

    if (mindmap_el_script) {
        markmap_div_html = markmap_div.outerHTML;
    }

    // render the mindmap if the script tag is present
    if (mindmap_el_script) {
        markmap.autoLoader.renderAll();
    }

    setTimeout(() => {
        var mindmap_el = document.querySelector('svg.markmap');

        var text_nodes = document.querySelectorAll("svg.markmap div");
        for (var i = 0; i < text_nodes.length; i++) {
            text_nodes[i].onclick = fillChatInput;
        }

        if (mindmap_el) {
            function on_svg_export(event) {
                html = "{html_template}";
                html = html.replace("{markmap_div}", markmap_div_html);
                spawnDocument(html, {window: "width=1000,height=1000"});
            }

            var link = document.getElementById("mindmap-toggle");
            if (link) {
                link.onclick = function(event) {
                    event.preventDefault(); // Prevent the default link behavior
                    var div = document.querySelector("div.markmap");
                    if (div) {
                        var currentHeight = div.style.height;
                        if (currentHeight === '400px' || (currentHeight === '')) {
                            div.style.height = '650px';
                        } else {
                            div.style.height = '400px'
                        }
                    }
                };
            }

            if (markmap_div_html) {
                var link = document.getElementById("mindmap-export");
                if (link) {
                    link.addEventListener('click', on_svg_export);
                }
            }
        }
    }, 250);

    // Auto-scroll answer panel to bottom when content updates
    setTimeout(() => {
        // Find the correct scrollable element - answer-panel is the scroll container
        var answer_panel = document.querySelector("#answer-panel");
        if (answer_panel) {
            // Check if this element itself scrolls
            if (answer_panel.scrollHeight > answer_panel.clientHeight) {
                answer_panel.scrollTo({
                    top: answer_panel.scrollHeight,
                    behavior: 'smooth'
                });
            } else {
                // Otherwise try direct children
                var children = answer_panel.children;
                for (var i = 0; i < children.length; i++) {
                    var child = children[i];
                    if (child && child.scrollHeight > child.clientHeight) {
                        child.scrollTo({
                            top: child.scrollHeight,
                            behavior: 'smooth'
                        });
                        break;
                    }
                }
            }
        }
    }, 30);
    
    // Setup MutationObserver to auto-scroll on content changes (real-time streaming)
    setTimeout(() => {
        var answer_expand = document.querySelector("#answer-expand");
        if (answer_expand) {
            var observer = new MutationObserver(function(mutations) {
                var answer_panel = document.querySelector("#answer-panel");
                if (answer_panel) {
                    // Scroll immediately without smooth animation for real-time following
                    if (answer_panel.scrollHeight > answer_panel.clientHeight) {
                        answer_panel.scrollTop = answer_panel.scrollHeight;
                    } else {
                        var children = answer_panel.children;
                        for (var i = 0; i < children.length; i++) {
                            var child = children[i];
                            if (child && child.scrollHeight > child.clientHeight) {
                                child.scrollTop = child.scrollHeight;
                                break;
                            }
                        }
                    }
                }
            });
            
            observer.observe(answer_expand, {
                childList: true,
                subtree: true,
                characterData: true
            });
        }
    }, 100);
    
    // Initialize drag-to-pan for all file previews
    setTimeout(() => {
        function initDragPan(container) {
            if (!container || container.dataset.dragInitialized === 'true') return;
            
            let isDragging = false;
            let startX = 0, startY = 0;
            let scrollLeft = 0, scrollTop = 0;
            
            const onMouseDown = (e) => {
                isDragging = true;
                startX = e.pageX - container.offsetLeft;
                startY = e.pageY - container.offsetTop;
                scrollLeft = container.scrollLeft;
                scrollTop = container.scrollTop;
                container.style.cursor = 'grabbing';
                container.style.userSelect = 'none';
                e.preventDefault();
            };
            
            const onMouseLeave = () => {
                isDragging = false;
                container.style.cursor = 'grab';
                container.style.userSelect = '';
            };
            
            const onMouseUp = () => {
                isDragging = false;
                container.style.cursor = 'grab';
                container.style.userSelect = '';
            };
            
            const onMouseMove = (e) => {
                if (!isDragging) return;
                e.preventDefault();
                const x = e.pageX - container.offsetLeft;
                const y = e.pageY - container.offsetTop;
                const walkX = (x - startX) * 1.5;
                const walkY = (y - startY) * 1.5;
                container.scrollLeft = scrollLeft - walkX;
                container.scrollTop = scrollTop - walkY;
            };
            
            container.addEventListener('mousedown', onMouseDown);
            container.addEventListener('mouseleave', onMouseLeave);
            container.addEventListener('mouseup', onMouseUp);
            container.addEventListener('mousemove', onMouseMove);
            
            container.dataset.dragInitialized = 'true';
        }
        
        ['.pdf-preview-shell', '.docx-preview', '.pptx-preview-shell', '.xlsx-preview-shell']
            .forEach(selector => {
                document.querySelectorAll(selector).forEach(el => initDragPan(el));
            });
    }, 150);

    return [links.length]
}
""".replace(
    "{html_template}",
    MINDMAP_HTML_EXPORT_TEMPLATE.replace("\n", "").replace('"', '\\"'),
)

fetch_api_key_js = """
function(_, __) {
    api_key = getStorage('google_api_key', '');
    return [api_key, _];
}
"""

# Auto-scroll answer panel to bottom
scroll_answer_panel_js = """
function() {
    setTimeout(() => {
        // Find the correct scrollable element - answer-panel is the scroll container
        var answer_panel = document.querySelector("#answer-panel");
        if (answer_panel) {
            if (answer_panel.scrollHeight > answer_panel.clientHeight) {
                answer_panel.scrollTop = answer_panel.scrollHeight;
            } else {
                var children = answer_panel.children;
                for (var i = 0; i < children.length; i++) {
                    var child = children[i];
                    if (child && child.scrollHeight > child.clientHeight) {
                        child.scrollTop = child.scrollHeight;
                        break;
                    }
                }
            }
        }
    }, 30);
}
"""

# Enable drag-to-pan for all file previews
preview_drag_pan_js = """
function() {
    function initDragPan(container) {
        if (!container || container.dataset.dragInitialized === 'true') return;
        
        let isDragging = false;
        let startX = 0, startY = 0;
        let scrollLeft = 0, scrollTop = 0;
        
        const onMouseDown = (e) => {
            isDragging = true;
            startX = e.pageX - container.offsetLeft;
            startY = e.pageY - container.offsetTop;
            scrollLeft = container.scrollLeft;
            scrollTop = container.scrollTop;
            container.style.cursor = 'grabbing';
            container.style.userSelect = 'none';
            e.preventDefault();
        };
        
        const onMouseLeave = () => {
            isDragging = false;
            container.style.cursor = 'grab';
            container.style.userSelect = '';
        };
        
        const onMouseUp = () => {
            isDragging = false;
            container.style.cursor = 'grab';
            container.style.userSelect = '';
        };
        
        const onMouseMove = (e) => {
            if (!isDragging) return;
            e.preventDefault();
            const x = e.pageX - container.offsetLeft;
            const y = e.pageY - container.offsetTop;
            const walkX = (x - startX) * 1.5; // Scroll speed multiplier
            const walkY = (y - startY) * 1.5;
            container.scrollLeft = scrollLeft - walkX;
            container.scrollTop = scrollTop - walkY;
        };
        
        // Touch support
        const onTouchStart = (e) => {
            if (e.touches.length !== 1) return;
            isDragging = true;
            const touch = e.touches[0];
            startX = touch.pageX - container.offsetLeft;
            startY = touch.pageY - container.offsetTop;
            scrollLeft = container.scrollLeft;
            scrollTop = container.scrollTop;
            e.preventDefault();
        };
        
        const onTouchEnd = () => {
            isDragging = false;
        };
        
        const onTouchMove = (e) => {
            if (!isDragging || e.touches.length !== 1) return;
            e.preventDefault();
            const touch = e.touches[0];
            const x = touch.pageX - container.offsetLeft;
            const y = touch.pageY - container.offsetTop;
            const walkX = (x - startX) * 1.5;
            const walkY = (y - startY) * 1.5;
            container.scrollLeft = scrollLeft - walkX;
            container.scrollTop = scrollTop - walkY;
        };
        
        // Mouse events
        container.addEventListener('mousedown', onMouseDown);
        container.addEventListener('mouseleave', onMouseLeave);
        container.addEventListener('mouseup', onMouseUp);
        container.addEventListener('mousemove', onMouseMove);
        
        // Touch events
        container.addEventListener('touchstart', onTouchStart, { passive: false });
        container.addEventListener('touchend', onTouchEnd);
        container.addEventListener('touchmove', onTouchMove, { passive: false });
        
        container.dataset.dragInitialized = 'true';
    }
    
    // Initialize on all preview containers
    setTimeout(() => {
        const selectors = [
            '.pdf-preview-shell',
            '.docx-preview',
            '.pptx-preview-shell',
            '.xlsx-preview-shell'
        ];
        
        selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => initDragPan(el));
        });
    }, 100);
}
"""


class ChatPage(BasePage):
    def __init__(self, app):
        self._app = app
        self._indices_input = []
        self.page_preview = ChatPagePreviewController(app)
        self.file_index = (
            self._app.index_manager.indices[0]
            if self._app.index_manager.indices
            else None
        )
        self.knowledge_graph = (
            GlobalKnowledgeGraphService(self._app, self.file_index)
            if self.file_index is not None
            else None
        )

        self.on_building_ui()

        self._preview_links = gr.State(value=None)
        self._reasoning_type = gr.State(value=None)
        self._conversation_renamed = gr.State(value=False)
        # Keep suggestion feature disabled in this layout to simplify the left sidebar.
        self._use_suggestion = gr.State(value=False)
        self._info_panel_expanded = gr.State(value=True)
        self._command_state = gr.State(value=None)
        self._user_api_key = gr.Text(value="", visible=False)
        # Active file information states
        self._active_file_id = gr.State(value="")
        self._active_file_name = gr.State(value="")
        self._active_file_path = gr.State(value="")
        self._active_file_total_pages = gr.State(value=1)
        # Page-level output cache for chat isolation: {file_id_page_num: {last_question, mindmap_html, answer_text, chat_history}}
        self._page_outputs_cache = gr.State(value={})
        # Last question asked about the current page
        self._last_question = gr.State(value="")
        # Request-scoped outputs for page-safe caching/persistence
        self._request_page_number = gr.State(value=1)
        self._request_file_id = gr.State(value="")
        self._request_last_question = gr.State(value="")
        self._request_info_html = gr.State(value="")
        self._request_answer_html = gr.State(value="")
        self._request_chat_history = gr.State(value=[])

    def on_building_ui(self):
        with gr.Row():
            # Chat history state (not used for page-level isolation)
            self.state_chat = gr.State(STATE)
            # Retrieval and plot history states
            self.state_retrieval_history = gr.State([])
            self.state_plot_history = gr.State([])
            self.state_plot_panel = gr.State(None)
            self._graph_source_ids = gr.State([])
            self.first_selector_choices = gr.State(None)
            # Selected text from the current page for targeted questions
            self._selected_page_text = gr.Textbox(
                value="", visible=False, elem_id="selected-page-text"
            )
            self._selected_graph_context = gr.Textbox(
                value="", visible=False, elem_id="selected-graph-context"
            )
            self._chat_file_click = gr.Textbox(
                value="", visible=False, elem_id="chat-file-click"
            )

            with gr.Column(scale=1, elem_id="conv-settings-panel") as self.conv_column:
                self.chat_control = ConversationControl(self._app)

                self.upload_scope_hint = gr.Markdown(
                    "**Sources in this conversation are treated as related by default.** "
                    "If files are weakly related, the knowledge graph will split them into separate systems.",
                    elem_id="chat-upload-hint",
                )
                with gr.Column(elem_id="chat-file-browser"):
                    self.chat_file_filter = gr.Textbox(
                        value="",
                        label="Files in this conversation",
                        placeholder="Filter file name",
                        elem_id="chat-file-filter",
                    )
                    self.chat_file_rows = gr.State([])
                    self.chat_selected_file = gr.Markdown(
                        "Focus: all files",
                        elem_id="chat-selected-file",
                    )
                    self.chat_file_list = gr.HTML(
                        "<div class='chat-file-empty'>No files uploaded</div>",
                        elem_id="chat-file-list",
                    )

                with gr.Accordion(
                    label="Advanced Source Selectors",
                    open=False,
                    elem_id="advanced-source-selectors",
                    visible=False,
                ):
                    for index_id, index in enumerate(self._app.index_manager.indices):
                        index.selector = None
                        index_ui = index.get_selector_component_ui()
                        if not index_ui:
                            # the index doesn't have a selector UI component
                            continue

                        index_ui.unrender()  # need to rerender later within Accordion
                        is_first_index = index_id == 0
                        index_name = index.name

                        if KH_DEMO_MODE and is_first_index:
                            index_name = "Select from Paper Collection"

                        with gr.Accordion(
                            label=index_name,
                            open=is_first_index,
                            elem_id=f"index-{index_id}",
                        ):
                            index_ui.render()
                            gr_index = index_ui.as_gradio_component()

                            # get the file selector choices for the first index
                            if index_id == 0:
                                self.first_selector_choices = index_ui.selector_choices
                                self.first_indexing_url_fn = None

                            if gr_index:
                                if isinstance(gr_index, list):
                                    index.selector = tuple(
                                        range(
                                            len(self._indices_input),
                                            len(self._indices_input) + len(gr_index),
                                        )
                                    )
                                    index.default_selector = index_ui.default()
                                    self._indices_input.extend(gr_index)
                                else:
                                    index.selector = len(self._indices_input)
                                    index.default_selector = index_ui.default()
                                    self._indices_input.append(gr_index)
                            setattr(self, f"_index_{index.id}", index_ui)

                self.chat_suggestion = ChatSuggestion(self._app, show_panel=False)

                if len(self._app.index_manager.indices) > 0:
                    quick_upload_label = (
                        "Quick Upload" if not KH_DEMO_MODE else "Or input new paper URL"
                    )

                    with gr.Accordion(label=quick_upload_label) as _:
                        self.quick_file_upload_status = gr.Markdown()
                        if not KH_DEMO_MODE:
                            self.quick_file_upload = File(
                                file_types=list(KH_DEFAULT_FILE_EXTRACTORS.keys()),
                                file_count="multiple",
                                container=True,
                                show_label=False,
                                elem_id="quick-file",
                            )
                        self.quick_urls = gr.Textbox(
                            placeholder=(
                                "Or paste URLs"
                                if not KH_DEMO_MODE
                                else "Paste Arxiv URLs\n(https://arxiv.org/abs/xxx)"
                            ),
                            lines=1,
                            container=False,
                            show_label=False,
                            elem_id=(
                                "quick-url" if not KH_DEMO_MODE else "quick-url-demo"
                            ),
                        )

                if not KH_DEMO_MODE:
                    self.report_issue = ReportIssue(self._app, show_panel=False)
                else:
                    with gr.Accordion(label="Related papers", open=False):
                        self.related_papers = gr.Markdown(elem_id="related-papers")

                    self.hint_page = HintPage(self._app)

            with gr.Column(scale=6, elem_id="chat-area"):
                if KH_DEMO_MODE:
                    self.paper_list = PaperListPage(self._app)

                with gr.Column(elem_id="chat-preview-section"):
                    self.chat_panel = ChatPanel(self._app)

                with gr.Column(elem_id="chat-bottom-controls"):
                    self.chat_panel.render_notice_and_pager()

                    with gr.Accordion(
                        label="Chat settings",
                        elem_id="chat-settings-expand",
                        open=False,
                        visible=not KH_DEMO_MODE,
                    ) as self.chat_settings:
                        with gr.Row(elem_id="quick-setting-labels"):
                            gr.HTML("Reasoning method")
                            gr.HTML(
                                "Model", visible=not KH_DEMO_MODE and not KH_SSO_ENABLED
                            )
                            gr.HTML("Language")

                        with gr.Row():
                            reasoning_setting = (
                                self._app.default_settings.reasoning.settings["use"]
                            )
                            model_setting = self._app.default_settings.reasoning.options[
                                "simple"
                            ].settings["llm"]
                            language_setting = (
                                self._app.default_settings.reasoning.settings["lang"]
                            )
                            citation_setting = self._app.default_settings.reasoning.options[
                                "simple"
                            ].settings["highlight_citation"]

                            self.reasoning_type = gr.Dropdown(
                                choices=reasoning_setting.choices[:REASONING_LIMITS],
                                value=reasoning_setting.value,
                                container=False,
                                show_label=False,
                            )
                            self.model_type = gr.Dropdown(
                                choices=model_setting.choices,
                                value=model_setting.value,
                                container=False,
                                show_label=False,
                                visible=not KH_DEMO_MODE and not KH_SSO_ENABLED,
                            )
                            self.language = gr.Dropdown(
                                choices=language_setting.choices,
                                value=language_setting.value,
                                container=False,
                                show_label=False,
                            )

                            self.citation = gr.Dropdown(
                                choices=citation_setting.choices,
                                value=citation_setting.value,
                                container=False,
                                show_label=False,
                                interactive=True,
                                elem_id="citation-dropdown",
                            )

                            if not config("USE_LOW_LLM_REQUESTS", default=False, cast=bool):
                                self.use_mindmap = gr.State(value=True)
                                self.use_mindmap_check = gr.Checkbox(
                                    label="Mindmap (on)",
                                    container=False,
                                    elem_id="use-mindmap-checkbox",
                                    value=True,
                                )
                            else:
                                self.use_mindmap = gr.State(value=False)
                                self.use_mindmap_check = gr.Checkbox(
                                    label="Mindmap (off)",
                                    container=False,
                                    elem_id="use-mindmap-checkbox",
                                    value=False,
                                )

                    self.chat_panel.render_input()

            with gr.Column(
                scale=INFO_PANEL_SCALES[False], elem_id="chat-info-panel"
            ) as self.info_column:
                with gr.Accordion(label="Knowledge Graph", open=True, elem_id="info-expand"):
                    self.modal = gr.HTML("<div id='pdf-modal'></div>")
                    self.knowledge_graph_status = gr.Markdown(
                        "Status: no graph generated yet.",
                        elem_id="knowledge-graph-status",
                    )
                    self.knowledge_graph_refresh = gr.Button(
                        "Generate / Refresh Knowledge Graph",
                        variant="secondary",
                        elem_id="knowledge-graph-refresh",
                    )
                    self.plot_panel = gr.HTML("", visible=True, elem_id="knowledge-graph-plot")
                    self.info_panel = gr.HTML(elem_id="html-info-panel")

                with gr.Accordion(label="Answer", open=True, elem_id="answer-expand"):
                    self.kg_answer_hint = gr.HTML(
                        value=(
                            "<div class='kg-answer-hint kg-answer-hint--empty'>"
                            "Select a node in the knowledge graph tree to pin context and get a suggested question."
                            "</div>"
                        ),
                        elem_id="kg-answer-hint",
                    )
                    self.answer_panel = gr.Markdown(value="", elem_id="answer-panel")

        self.followup_questions = self.chat_suggestion.examples
        self.followup_questions_ui = self.chat_suggestion.accordion

    def _json_to_plot(self, json_dict: dict | None):
        html_payload = ""
        if isinstance(json_dict, dict):
            if "html" in json_dict:
                html_payload = str(json_dict.get("html", "") or "")
            else:
                try:
                    html_payload = html.escape(json.dumps(json_dict, ensure_ascii=False))
                except Exception:
                    html_payload = ""
        elif isinstance(json_dict, str):
            html_payload = json_dict
        return gr.update(visible=True, value=html_payload)

    @staticmethod
    def _normalize_selected_file_ids(selected_file_ids) -> list[str]:
        if selected_file_ids in (None, ""):
            return []
        if isinstance(selected_file_ids, list):
            return [str(item) for item in selected_file_ids if item not in (None, "")]
        return [str(selected_file_ids)]

    @staticmethod
    def _merge_unique_file_ids(*groups) -> list[str]:
        merged: list[str] = []
        seen = set()
        for group in groups:
            if group in (None, ""):
                continue
            values = group if isinstance(group, list) else [group]
            for value in values:
                item = str(value or "").strip()
                if not item or item in seen:
                    continue
                seen.add(item)
                merged.append(item)
        return merged

    @staticmethod
    def _extract_selected_ids_from_data_source(data_source: dict | None) -> list[str]:
        if not isinstance(data_source, dict):
            return []

        selected = data_source.get("selected", {})
        if not isinstance(selected, dict):
            return []

        file_ids: list[str] = []
        for value in selected.values():
            candidates = value if isinstance(value, list) else [value]
            for candidate in candidates:
                if isinstance(candidate, list):
                    for nested in candidate:
                        if isinstance(nested, (dict, tuple, list)):
                            continue
                        item = str(nested or "").strip()
                        if not item:
                            continue
                        if item.lower() in {"select", "upload", "all"}:
                            continue
                        file_ids.append(item)
                else:
                    if isinstance(candidate, (dict, tuple)):
                        continue
                    item = str(candidate or "").strip()
                    if not item:
                        continue
                    if item.lower() in {"select", "upload", "all"}:
                        continue
                    file_ids.append(item)
        return ChatPage._merge_unique_file_ids(file_ids)

    def merge_graph_source_ids(self, graph_source_ids, new_file_ids):
        return self._merge_unique_file_ids(
            self._normalize_selected_file_ids(graph_source_ids),
            self._normalize_selected_file_ids(new_file_ids),
        )

    @staticmethod
    def _is_group_selector_value(selector_value: str) -> bool:
        value = str(selector_value or "").strip()
        return value.startswith("[") and value.endswith("]")

    def _build_selector_source_map(self, first_selector_choices) -> dict[str, str]:
        source_map: dict[str, str] = {}
        for item in list(first_selector_choices or []):
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            name = str(item[0] or "")
            file_id = str(item[1] or "")
            if not file_id or self._is_group_selector_value(file_id):
                continue
            source_map[file_id] = name or file_id
        return source_map

    def _load_available_source_map(self, user_id) -> dict[str, str]:
        source_map: dict[str, str] = {}
        if not self.file_index:
            return source_map

        Source = self.file_index._resources.get("Source")
        if Source is None:
            return source_map

        try:
            with Session(engine) as session:
                statement = select(Source)
                if self.file_index.config.get("private", False):
                    statement = statement.where(Source.user == user_id)

                rows = session.execute(statement).all()
                for row in rows:
                    item = None
                    if isinstance(row, (list, tuple)):
                        item = row[0] if row else None
                    elif hasattr(row, "_mapping"):
                        mapping = getattr(row, "_mapping")
                        if Source in mapping:
                            item = mapping[Source]
                        elif mapping:
                            item = next(iter(mapping.values()))
                    if item is None:
                        item = row

                    file_id = str(getattr(item, "id", "") or "")
                    if not file_id:
                        continue
                    file_name = str(getattr(item, "name", "") or file_id)
                    source_map[file_id] = file_name
        except Exception as exc:
            logger.warning("Failed to load source map for chat sidebar: %s", exc)

        return source_map

    def sync_graph_source_ids_with_selector_choices(
        self,
        graph_source_ids,
        first_selector_choices,
        user_id,
    ):
        current_ids = self._normalize_selected_file_ids(graph_source_ids)
        if not current_ids:
            return []

        source_map = self._load_available_source_map(user_id)
        if not source_map:
            source_map = self._build_selector_source_map(first_selector_choices)
        if not source_map:
            # Selector choices might not be loaded yet during startup.
            return current_ids

        available_ids = set(source_map.keys())
        return [file_id for file_id in current_ids if file_id in available_ids]

    def persist_conversation_source_scope(
        self,
        conversation_id,
        user_id,
        graph_source_ids,
    ):
        normalized_ids = self._normalize_selected_file_ids(graph_source_ids)
        if not conversation_id:
            return normalized_ids

        try:
            with Session(engine) as session:
                statement = select(Conversation).where(Conversation.id == conversation_id)
                row = session.exec(statement).one_or_none()
                if not row:
                    return normalized_ids

                if row.user not in (None, user_id):
                    return normalized_ids

                data_source = dict(row.data_source or {})
                existing_ids = self._normalize_selected_file_ids(
                    data_source.get("graph_source_ids", [])
                )
                if existing_ids == normalized_ids:
                    return normalized_ids

                data_source["graph_source_ids"] = normalized_ids
                row.data_source = data_source
                session.add(row)
                session.commit()
        except Exception as exc:
            logger.warning("Failed to persist conversation source scope: %s", exc)

        return normalized_ids

    def _render_chat_file_list_html(self, rows: list[dict], selected_ids: set[str]) -> str:
        if not rows:
            return "<div class='chat-file-empty'>No files uploaded</div>"

        items = []
        for row in rows:
            file_id = str(row.get("id", "") or "")
            file_name = str(row.get("name", "") or file_id)
            is_selected = file_id in selected_ids
            item_class = "chat-file-entry is-selected" if is_selected else "chat-file-entry"
            items.append(
                f"<button type='button' class='{item_class}' data-chat-file-id='{html.escape(file_id, quote=True)}'>"
                "<span class='chat-file-entry__name'>"
                f"{html.escape(file_name)}"
                "</span>"
                "</button>"
            )

        return "<div class='chat-file-list-shell'>" + "".join(items) + "</div>"

    def refresh_chat_file_list(
        self,
        conversation_id,
        user_id,
        first_selector_choices,
        selected_file_ids,
        graph_source_ids,
        filter_text,
    ):
        selected_ids = self._normalize_selected_file_ids(selected_file_ids)
        selected_set = set(selected_ids)
        keyword = str(filter_text or "").strip().lower()
        source_map = self._load_available_source_map(user_id)
        if not source_map and not str(conversation_id or "").strip():
            source_map = self._build_selector_source_map(first_selector_choices)

        scoped_ids = self._normalize_selected_file_ids(graph_source_ids)
        if not scoped_ids:
            # Backward-compatible fallback for older conversations.
            scoped_ids = selected_ids

        if source_map and scoped_ids:
            available_ids = set(source_map.keys())
            scoped_ids = [file_id for file_id in scoped_ids if file_id in available_ids]

        if not scoped_ids and not str(conversation_id or "").strip():
            # No active conversation yet: show all available files in collection.
            scoped_ids = list(source_map.keys())

        rows: list[dict] = []
        for file_id in scoped_ids:
            name = source_map.get(file_id, file_id)
            if keyword and keyword not in name.lower():
                continue
            rows.append({"id": file_id, "name": name})

        selected_name = "all files in conversation"
        if selected_ids:
            first_selected = selected_ids[0]
            for row in rows:
                if row["id"] == first_selected:
                    selected_name = row["name"]
                    break
            if selected_name == "all files in conversation":
                selected_name = source_map.get(first_selected, first_selected)
        elif not str(conversation_id or "").strip():
            selected_name = "all files in collection"

        list_html = self._render_chat_file_list_html(rows, selected_set)
        return rows, list_html, f"Focus: {selected_name}"

    def select_chat_file(self, file_id):
        target_id = str(file_id or "").strip()
        if not target_id:
            return gr.update(), gr.update(), ""
        return "select", gr.update(value=[target_id]), ""

    def load_conversation_graph_state(self, conversation_id):
        if not conversation_id:
            return []
        try:
            with Session(engine) as session:
                statement = select(Conversation).where(Conversation.id == conversation_id)
                result = session.exec(statement).one_or_none()
        except Exception:
            return []
        if not result:
            return []
        data_source = dict(result.data_source or {})
        value = self._normalize_selected_file_ids(data_source.get("graph_source_ids", []))
        if value:
            return value

        fallback_ids = self._extract_selected_ids_from_data_source(data_source)
        if fallback_ids:
            data_source["graph_source_ids"] = fallback_ids
            try:
                with Session(engine) as session:
                    statement = select(Conversation).where(Conversation.id == conversation_id)
                    row = session.exec(statement).one_or_none()
                    if row:
                        row.data_source = data_source
                        session.add(row)
                        session.commit()
            except Exception:
                pass
        return fallback_ids

    def refresh_knowledge_graph(
        self,
        conversation_id,
        graph_source_ids,
        focus_file_id,
    ):
        if not self.knowledge_graph:
            return gr.update(value=""), None, "Status: knowledge graph unavailable.", []
        source_scope = self._normalize_selected_file_ids(graph_source_ids)
        try:
            graph_view = self.knowledge_graph.get_graph_view(
                conversation_id=conversation_id,
                graph_source_ids=source_scope,
                focus_file_id=focus_file_id,
                force_rebuild=False,
            )
            return (
                self._json_to_plot(graph_view),
                graph_view,
                f"Status: {graph_view.get('status_message', 'ready')}",
                graph_view.get("graph_source_ids", []),
            )
        except Exception as exc:
            logger.warning("Failed to refresh knowledge graph: %s", exc)
            return (
                gr.update(value=""),
                None,
                "Status: failed to load knowledge graph.",
                self._normalize_selected_file_ids(source_scope),
            )

    def auto_refresh_knowledge_graph(
        self,
        conversation_id,
        graph_source_ids,
        focus_file_id,
    ):
        # Keep backward compatibility with existing event wiring but do not force rebuild.
        return self.refresh_knowledge_graph(
            conversation_id=conversation_id,
            graph_source_ids=graph_source_ids,
            focus_file_id=focus_file_id,
        )

    def generate_knowledge_graph(
        self,
        conversation_id,
        graph_source_ids,
        focus_file_id,
    ):
        if not self.knowledge_graph:
            return gr.update(value=""), None, "Status: knowledge graph unavailable.", []
        source_scope = self._normalize_selected_file_ids(graph_source_ids)
        try:
            graph_view = self.knowledge_graph.get_graph_view(
                conversation_id=conversation_id,
                graph_source_ids=source_scope,
                focus_file_id=focus_file_id,
                force_rebuild=True,
            )
            return (
                self._json_to_plot(graph_view),
                graph_view,
                f"Status: {graph_view.get('status_message', 'ready')}",
                graph_view.get("graph_source_ids", []),
            )
        except Exception as exc:
            logger.warning("Failed to generate knowledge graph: %s", exc)
            return (
                gr.update(value=""),
                None,
                "Status: failed to generate knowledge graph.",
                self._normalize_selected_file_ids(source_scope),
            )

    def _format_chat_message(self, content: str, role: str) -> str:
        """Format a chat message as a bubble"""
        import html
        
        escaped_content = html.escape(content)
        # Replace newlines with <br> for proper line breaks
        formatted_content = escaped_content.replace('\n', '<br>')
        return f'<div class="chat-message {role}"><div class="chat-message-content">{formatted_content}</div></div>'

    def _generate_answer_panel_html(self, preserved_history: list, user_input: str, ai_response: str, is_thinking: bool = False) -> str:
        """Generate HTML for answer panel with chat bubbles"""
        messages_html = ""
        
        # Add preserved history (previous Q&A on the same page)
        for item in preserved_history:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                user_msg, ai_msg = item
                if user_msg:
                    messages_html += self._format_chat_message(str(user_msg), "user")
                if ai_msg:
                    messages_html += self._format_chat_message(str(ai_msg), "assistant")
                # Add separator between conversation turns
                messages_html += '<div style="height: 8px;"></div>'
        
        # Add current exchange
        if user_input:
            messages_html += self._format_chat_message(user_input, "user")
        
        if is_thinking:
            messages_html += '<div class="chat-message assistant"><div class="chat-message-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div></div>'
        elif ai_response:
            messages_html += self._format_chat_message(ai_response, "assistant")
        
        return messages_html

    def rerun_page_answer(
        self,
        last_question,
        conversation_id,
        chat_history,
        settings,
        reasoning_type,
        llm_type,
        use_mind_map,
        use_citation,
        language,
        chat_state,
        command_state,
        user_id,
        active_file_id,
        active_file_name,
        page_number,
        selected_page_text,
        *selecteds,
    ):
        if not last_question:
            return (
                chat_history,
                gr.update(),
                gr.update(visible=False),
                None,
                chat_state,
                "",
                max(1, int(page_number or 1)),
                active_file_id or "",
                "",
                "",
                "",
                [],
            )

        rerun_history = chat_history
        if rerun_history and rerun_history[-1][0] == last_question:
            rerun_history = rerun_history[:-1] + [(last_question, None)]
        else:
            rerun_history = rerun_history + [(last_question, None)]

        final_output = None
        for output in self.chat_fn(
            conversation_id,
            rerun_history,
            settings,
            reasoning_type,
            llm_type,
            use_mind_map,
            use_citation,
            language,
            chat_state,
            command_state,
            user_id,
            active_file_id,
            active_file_name,
            page_number,
            selected_page_text,
            *selecteds,
        ):
            final_output = output

        if final_output is None:
            return (
                chat_history,
                gr.update(),
                gr.update(visible=False),
                None,
                chat_state,
                "",
                max(1, int(page_number or 1)),
                active_file_id or "",
                "",
                "",
                "",
                [],
            )

        return final_output

    def on_register_events(self):
        # first index paper recommendation
        if KH_DEMO_MODE and len(self._indices_input) > 0:
            self._indices_input[1].change(
                self.get_recommendations,
                inputs=[self.first_selector_choices, self._indices_input[1]],
                outputs=[self.related_papers],
            ).then(
                fn=None,
                inputs=None,
                outputs=None,
                js=recommended_papers_js,
            )

        if len(self._indices_input) > 1:
            self._indices_input[1].change(
                fn=self.page_preview.on_selected_file_change,
                inputs=[
                    self.first_selector_choices,
                    self._indices_input[1],
                    self._page_outputs_cache,
                ],
                outputs=[
                    self._active_file_id,
                    self._active_file_name,
                    self._active_file_path,
                    self.chat_panel.page_number,
                    self._active_file_total_pages,
                    self.chat_panel.pdf_preview_src,
                    self.chat_panel.pdf_preview_notice,
                    self._last_question,
                    self.info_panel,
                    self.plot_panel,
                    self.state_plot_panel,
                    self.answer_panel,
                    self.chat_panel.chatbot,
                    self._page_outputs_cache,
                ],
                show_progress="hidden",
            ).then(
                fn=lambda: "",
                outputs=[self._selected_page_text],
                show_progress="hidden",
            ).then(
                fn=lambda: True,
                inputs=None,
                outputs=[self._preview_links],
                js=pdfview_js,
            )

        self.chat_panel.preview_refresh_timer.tick(
            fn=self.page_preview.on_preview_tick,
            inputs=[
                self._active_file_id,
                self._active_file_name,
                self._active_file_path,
                self.chat_panel.page_number,
                self._active_file_total_pages,
                self.chat_panel.pdf_preview_src,
                self.chat_panel.pdf_preview_notice,
            ],
            outputs=[
                self.chat_panel.page_number,
                self._active_file_total_pages,
                self.chat_panel.pdf_preview_src,
                self.chat_panel.pdf_preview_notice,
            ],
            show_progress="hidden",
        )

        self.chat_panel.prev_page_btn.click(
            fn=self.page_preview.on_prev_page,
            inputs=[
                self.chat_panel.page_number,
                self._active_file_id,
                self._active_file_path,
                self._page_outputs_cache,
                self._active_file_total_pages,
            ],
            outputs=[
                self.chat_panel.page_number,
                self._active_file_total_pages,
                self.chat_panel.pdf_preview_src,
                self.chat_panel.pdf_preview_notice,
                self._last_question,
                self.info_panel,
                self.plot_panel,
                self.state_plot_panel,
                self.answer_panel,
                self.chat_panel.chatbot,  # Add chatbot to restore page-specific history
            ],
            show_progress="hidden",
        ).then(
            fn=lambda: "",
            outputs=[self._selected_page_text],
            show_progress="hidden",
        ).then(
            fn=lambda: True,
            inputs=None,
            outputs=[self._preview_links],
            js=pdfview_js,
        )

        self.chat_panel.next_page_btn.click(
            fn=self.page_preview.on_next_page,
            inputs=[
                self.chat_panel.page_number,
                self._active_file_id,
                self._active_file_path,
                self._page_outputs_cache,
                self._active_file_total_pages,
            ],
            outputs=[
                self.chat_panel.page_number,
                self._active_file_total_pages,
                self.chat_panel.pdf_preview_src,
                self.chat_panel.pdf_preview_notice,
                self._last_question,
                self.info_panel,
                self.plot_panel,
                self.state_plot_panel,
                self.answer_panel,
                self.chat_panel.chatbot,  # Add chatbot to restore page-specific history
            ],
            show_progress="hidden",
        ).then(
            fn=lambda: "",
            outputs=[self._selected_page_text],
            show_progress="hidden",
        ).then(
            fn=lambda: True,
            inputs=None,
            outputs=[self._preview_links],
            js=pdfview_js,
        )

        self.chat_panel.page_number.change(
            fn=self.page_preview.on_page_set,
            inputs=[
                self.chat_panel.page_number,
                self._active_file_id,
                self._active_file_path,
                self._page_outputs_cache,
                self._active_file_total_pages,
            ],
            outputs=[
                self.chat_panel.page_number,
                self._active_file_total_pages,
                self.chat_panel.pdf_preview_src,
                self.chat_panel.pdf_preview_notice,
                self._last_question,
                self.info_panel,
                self.plot_panel,
                self.state_plot_panel,
                self.answer_panel,
                self.chat_panel.chatbot,  # Add chatbot to restore page-specific history
            ],
            show_progress="hidden",
        ).then(
            fn=lambda: "",
            outputs=[self._selected_page_text],
            show_progress="hidden",
        ).then(
            fn=lambda: True,
            inputs=None,
            outputs=[self._preview_links],
            js=pdfview_js,
        )

        chat_event = (
            gr.on(
                triggers=[
                    self.chat_panel.text_input.submit,
                ],
                fn=self.submit_msg,
                inputs=[
                    self.chat_panel.text_input,
                    self.chat_panel.chatbot,
                    self._app.user_id,
                    self._app.settings_state,
                    self.chat_control.conversation_id,
                    self.chat_control.conversation_rn,
                    self.first_selector_choices,
                    self._graph_source_ids,
                    self._selected_page_text,
                    self._selected_graph_context,
                ],
                outputs=[
                    self.chat_panel.text_input,
                    self.chat_panel.chatbot,
                    self.chat_control.conversation_id,
                    self.chat_control.conversation,
                    self.chat_control.conversation_rn,
                    # file selector from the first index
                    self._indices_input[0],
                    self._indices_input[1],
                    self._last_question,
                    self._command_state,
                    self._selected_page_text,
                    self._selected_graph_context,
                    self._graph_source_ids,
                ],
                concurrency_limit=20,
                show_progress="hidden",
            )
            .success(
                fn=self.chat_fn,
                inputs=[
                    self.chat_control.conversation_id,
                    self.chat_panel.chatbot,
                    self._app.settings_state,
                    self._reasoning_type,
                    self.model_type,
                    self.use_mindmap,
                    self.citation,
                    self.language,
                    self.state_chat,
                    self._command_state,
                    self._app.user_id,
                    self._active_file_id,
                    self._active_file_name,
                    self.chat_panel.page_number,
                    self._selected_page_text,
                    self._selected_graph_context,
                    self.state_plot_panel,
                ]
                + self._indices_input,
                outputs=[
                    self.chat_panel.chatbot,
                    self.info_panel,
                    self.plot_panel,
                    self.state_plot_panel,
                    self.state_chat,
                    self.answer_panel,
                    self._request_page_number,
                    self._request_file_id,
                    self._request_last_question,
                    self._request_info_html,
                    self._request_answer_html,
                    self._request_chat_history,
                ],
                concurrency_limit=20,
                show_progress="minimal",
            )
            .success(
                fn=self.page_preview.cache_page_outputs,
                inputs=[
                    self._page_outputs_cache,
                    self._request_page_number,
                    self._request_last_question,
                    self._request_info_html,
                    self._request_answer_html,
                    self._request_file_id,
                    self._request_chat_history,  # Pass request-scoped chat history
                ],
                outputs=[self._page_outputs_cache],
                show_progress="hidden",
            )
            .then(
                fn=lambda: "",
                outputs=[self._selected_page_text],
                show_progress="hidden",
            )
            .then(
                fn=lambda: True,
                inputs=None,
                outputs=[self._preview_links],
                js=pdfview_js,  # 这里已经包含了自动滚动和拖动初始化
            )
            .then(
                fn=None,
                inputs=None,
                outputs=None,
                js=scroll_answer_panel_js,
            )
            .success(
                fn=self.check_and_suggest_name_conv,
                inputs=self._request_chat_history,
                outputs=[
                    self.chat_control.conversation_rn,
                    self._conversation_renamed,
                ],
            )
            .success(
                self.chat_control.rename_conv,
                inputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation_rn,
                    self._conversation_renamed,
                    self._app.user_id,
                ],
                outputs=[
                    self.chat_control.conversation,
                    self.chat_control.conversation,
                    self.chat_control.conversation_rn,
                ],
                show_progress="hidden",
            )
        )

        onSuggestChatEvent = {
            "fn": self.suggest_chat_conv,
            "inputs": [
                self._app.settings_state,
                self.language,
                self.chat_panel.chatbot,
                self._use_suggestion,
            ],
            "outputs": [
                self.followup_questions_ui,
                self.followup_questions,
            ],
            "show_progress": "hidden",
        }
        # chat_event = chat_event.success(**onSuggestChatEvent)

        # final data persist
        if not KH_DEMO_MODE:
            chat_event = chat_event.then(
                fn=self.persist_data_source,
                inputs=[
                    self.chat_control.conversation_id,
                    self._app.user_id,
                    self._request_info_html,
                    self.state_plot_panel,
                    self.state_retrieval_history,
                    self.state_plot_history,
                    self._request_chat_history,
                    self.state_chat,
                    self._graph_source_ids,
                ]
                + self._indices_input,
                outputs=[
                    self.state_retrieval_history,
                    self.state_plot_history,
                ],
                concurrency_limit=20,
            )

        self.chat_control.btn_info_expand.click(
            fn=lambda is_expanded: (
                gr.update(scale=INFO_PANEL_SCALES[is_expanded]),
                not is_expanded,
            ),
            inputs=self._info_panel_expanded,
            outputs=[self.info_column, self._info_panel_expanded],
        )
        self.chat_control.btn_chat_expand.click(
            fn=None, inputs=None, js="function() {toggleChatColumn();}"
        )

        if KH_DEMO_MODE:
            self.chat_control.btn_demo_logout.click(
                fn=None,
                js=self.chat_control.logout_js,
            )
            self.chat_control.btn_new.click(
                fn=lambda: self.chat_control.select_conv("", None),
                outputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation,
                    self.chat_control.conversation_rn,
                    self.chat_panel.chatbot,
                    self.followup_questions,
                    self.info_panel,
                    self.state_plot_panel,
                    self.state_retrieval_history,
                    self.state_plot_history,
                    self.chat_control.cb_is_public,
                    self.state_chat,
                ]
                + self._indices_input,
            ).then(
                lambda: (gr.update(visible=False), gr.update(visible=True)),
                outputs=[self.paper_list.accordion, self.chat_settings],
            ).then(
                fn=lambda: "",
                outputs=[self.answer_panel],
            ).then(
                fn=lambda: "",
                outputs=[self._last_question],
            ).then(
                fn=self.suggest_chat_conv,
                inputs=[
                    self._app.settings_state,
                    self.language,
                    self.chat_panel.chatbot,
                    self._use_suggestion,
                ],
                outputs=[
                    self.followup_questions_ui,
                    self.followup_questions,
                ],
            ).then(
                fn=None,
                inputs=None,
                js=chat_input_focus_js,
            )

        if not KH_DEMO_MODE:
            self.chat_control.btn_new.click(
                self.chat_control.new_conv,
                inputs=self._app.user_id,
                outputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation,
                ],
                show_progress="hidden",
            ).then(
                self.chat_control.select_conv,
                inputs=[self.chat_control.conversation, self._app.user_id],
                outputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation,
                    self.chat_control.conversation_rn,
                    self.chat_panel.chatbot,
                    self.followup_questions,
                    self.info_panel,
                    self.state_plot_panel,
                    self.state_retrieval_history,
                    self.state_plot_history,
                    self.chat_control.cb_is_public,
                    self.state_chat,
                ]
                + self._indices_input,
                show_progress="hidden",
            ).then(
                fn=self._json_to_plot,
                inputs=self.state_plot_panel,
                outputs=self.plot_panel,
            ).then(
                fn=lambda: "",
                outputs=[self.answer_panel],
            ).then(
                fn=lambda: "",
                outputs=[self._last_question],
            ).then(
                fn=self.suggest_chat_conv,
                inputs=[
                    self._app.settings_state,
                    self.language,
                    self.chat_panel.chatbot,
                    self._use_suggestion,
                ],
                outputs=[
                    self.followup_questions_ui,
                    self.followup_questions,
                ],
            ).then(
                fn=None,
                inputs=None,
                js=chat_input_focus_js,
            )

            self.chat_control.btn_del.click(
                lambda id: self.toggle_delete(id),
                inputs=[self.chat_control.conversation_id],
                outputs=[
                    self.chat_control._new_delete,
                    self.chat_control._delete_confirm,
                ],
            )
            self.chat_control.btn_del_conf.click(
                self.chat_control.delete_conv,
                inputs=[self.chat_control.conversation_id, self._app.user_id],
                outputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation,
                ],
                show_progress="hidden",
            ).then(
                self.chat_control.select_conv,
                inputs=[self.chat_control.conversation, self._app.user_id],
                outputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation,
                    self.chat_control.conversation_rn,
                    self.chat_panel.chatbot,
                    self.followup_questions,
                    self.info_panel,
                    self.state_plot_panel,
                    self.state_retrieval_history,
                    self.state_plot_history,
                    self.chat_control.cb_is_public,
                    self.state_chat,
                ]
                + self._indices_input,
                show_progress="hidden",
            ).then(
                fn=self._json_to_plot,
                inputs=self.state_plot_panel,
                outputs=self.plot_panel,
            ).then(
                lambda: self.toggle_delete(""),
                outputs=[
                    self.chat_control._new_delete,
                    self.chat_control._delete_confirm,
                ],
            )
            self.chat_control.btn_del_cnl.click(
                lambda: self.toggle_delete(""),
                outputs=[
                    self.chat_control._new_delete,
                    self.chat_control._delete_confirm,
                ],
            )
            self.chat_control.btn_conversation_rn.click(
                lambda: gr.update(visible=True),
                outputs=[
                    self.chat_control.conversation_rn,
                ],
            )
            self.chat_control.conversation_rn.submit(
                self.chat_control.rename_conv,
                inputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation_rn,
                    gr.State(value=True),
                    self._app.user_id,
                ],
                outputs=[
                    self.chat_control.conversation,
                    self.chat_control.conversation,
                    self.chat_control.conversation_rn,
                ],
                show_progress="hidden",
            )

        onConvSelect = (
            self.chat_control.conversation.select(
                self.chat_control.select_conv,
                inputs=[self.chat_control.conversation, self._app.user_id],
                outputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation,
                    self.chat_control.conversation_rn,
                    self.chat_panel.chatbot,
                    self.followup_questions,
                    self.info_panel,
                    self.state_plot_panel,
                    self.state_retrieval_history,
                    self.state_plot_history,
                    self.chat_control.cb_is_public,
                    self.state_chat,
                ]
                + self._indices_input,
                show_progress="hidden",
            )
            .then(
                fn=self._json_to_plot,
                inputs=self.state_plot_panel,
                outputs=self.plot_panel,
            )
            .then(
                lambda: self.toggle_delete(""),
                outputs=[
                    self.chat_control._new_delete,
                    self.chat_control._delete_confirm,
                ],
            )
            .then(
                fn=self.suggest_chat_conv,
                inputs=[
                    self._app.settings_state,
                    self.language,
                    self.chat_panel.chatbot,
                    self._use_suggestion,
                ],
                outputs=[
                    self.followup_questions_ui,
                    self.followup_questions,
                ],
            )
        )

        if KH_DEMO_MODE:
            onConvSelect = onConvSelect.then(
                lambda: (gr.update(visible=False), gr.update(visible=True)),
                outputs=[self.paper_list.accordion, self.chat_settings],
            )

        onConvSelect = (
            onConvSelect.then(
                fn=self.page_preview.refresh_selected_file_preview,
                inputs=[
                    self.first_selector_choices,
                    self._indices_input[1],
                    self.chat_panel.page_number,
                    self._active_file_total_pages,
                ],
                outputs=[
                    self._active_file_id,
                    self._active_file_name,
                    self._active_file_path,
                    self.chat_panel.page_number,
                    self._active_file_total_pages,
                    self.chat_panel.pdf_preview_src,
                    self.chat_panel.pdf_preview_notice,
                ],
                show_progress="hidden",
            )
            .then(
                fn=lambda: True,
                js=clear_bot_message_selection_js,
            )
            .then(
                fn=lambda: "",
                outputs=[self._selected_page_text],
                show_progress="hidden",
            )
            .then(
                fn=lambda: True,
                inputs=None,
                outputs=[self._preview_links],
                js=pdfview_js,
            )
            .then(
                fn=lambda history: history[-1][1] if history else "",
                inputs=[self.chat_panel.chatbot],
                outputs=[self.answer_panel],
                show_progress="hidden",
            )
            .then(
                fn=lambda history: history[-1][0] if history else "",
                inputs=[self.chat_panel.chatbot],
                outputs=[self._last_question],
                show_progress="hidden",
            )
            .then(fn=None, inputs=None, outputs=None, js=chat_input_focus_js)
        )

        if not KH_DEMO_MODE:
            # evidence display on message selection
            self.chat_panel.chatbot.select(
                self.message_selected,
                inputs=[
                    self.state_retrieval_history,
                    self.state_plot_history,
                ],
                outputs=[
                    self.info_panel,
                    self.state_plot_panel,
                ],
            ).then(
                fn=self._json_to_plot,
                inputs=self.state_plot_panel,
                outputs=self.plot_panel,
            ).then(
                fn=lambda: True,
                inputs=None,
                outputs=[self._preview_links],
                js=pdfview_js,
            )

        self.chat_control.cb_is_public.change(
            self.on_set_public_conversation,
            inputs=[self.chat_control.cb_is_public, self.chat_control.conversation],
            outputs=None,
            show_progress="hidden",
        )

        if not KH_DEMO_MODE:
            # user feedback events
            self.chat_panel.chatbot.like(
                fn=self.is_liked,
                inputs=[self.chat_control.conversation_id],
                outputs=None,
            )
            self.report_issue.report_btn.click(
                self.report_issue.report,
                inputs=[
                    self.report_issue.correctness,
                    self.report_issue.issues,
                    self.report_issue.more_detail,
                    self.chat_control.conversation_id,
                    self.chat_panel.chatbot,
                    self._app.settings_state,
                    self._app.user_id,
                    self.info_panel,
                    self.state_chat,
                ]
                + self._indices_input,
                outputs=None,
            )

        self.reasoning_type.change(
            self.reasoning_changed,
            inputs=[self.reasoning_type],
            outputs=[self._reasoning_type],
        )
        self.use_mindmap_check.change(
            lambda x: (x, gr.update(label="Mindmap " + ("(on)" if x else "(off)"))),
            inputs=[self.use_mindmap_check],
            outputs=[self.use_mindmap, self.use_mindmap_check],
            show_progress="hidden",
        )

        def toggle_chat_suggestion(current_state):
            return current_state, gr.update(visible=current_state)

        def raise_error_on_state(state):
            if not state:
                raise ValueError("Chat suggestion disabled")

        self.chat_control.cb_suggest_chat.change(
            fn=toggle_chat_suggestion,
            inputs=[self.chat_control.cb_suggest_chat],
            outputs=[self._use_suggestion, self.followup_questions_ui],
            show_progress="hidden",
        ).then(
            fn=raise_error_on_state,
            inputs=[self._use_suggestion],
            show_progress="hidden",
        ).success(
            **onSuggestChatEvent
        )
        self.chat_control.conversation_id.change(
            lambda: gr.update(visible=False),
            outputs=self.plot_panel,
        )

        self.followup_questions.select(
            self.chat_suggestion.select_example,
            outputs=[self.chat_panel.text_input],
            show_progress="hidden",
        ).then(
            fn=None,
            inputs=None,
            outputs=None,
            js=chat_input_focus_js,
        )

        if self.knowledge_graph and len(self._indices_input) > 1:
            self.chat_file_filter.change(
                fn=self.refresh_chat_file_list,
                inputs=[
                    self.chat_control.conversation_id,
                    self._app.user_id,
                    self.first_selector_choices,
                    self._indices_input[1],
                    self._graph_source_ids,
                    self.chat_file_filter,
                ],
                outputs=[
                    self.chat_file_rows,
                    self.chat_file_list,
                    self.chat_selected_file,
                ],
                show_progress="hidden",
            )

            self._indices_input[1].change(
                fn=self.refresh_chat_file_list,
                inputs=[
                    self.chat_control.conversation_id,
                    self._app.user_id,
                    self.first_selector_choices,
                    self._indices_input[1],
                    self._graph_source_ids,
                    self.chat_file_filter,
                ],
                outputs=[
                    self.chat_file_rows,
                    self.chat_file_list,
                    self.chat_selected_file,
                ],
                show_progress="hidden",
            ).then(
                fn=self.refresh_knowledge_graph,
                inputs=[
                    self.chat_control.conversation_id,
                    self._graph_source_ids,
                    self._active_file_id,
                ],
                outputs=[
                    self.plot_panel,
                    self.state_plot_panel,
                    self.knowledge_graph_status,
                    self._graph_source_ids,
                ],
                show_progress="hidden",
            )

            self._chat_file_click.change(
                fn=self.select_chat_file,
                inputs=[self._chat_file_click],
                outputs=[
                    self._indices_input[0],
                    self._indices_input[1],
                    self._chat_file_click,
                ],
                show_progress="hidden",
            )

            self.first_selector_choices.change(
                fn=self.sync_graph_source_ids_with_selector_choices,
                inputs=[
                    self._graph_source_ids,
                    self.first_selector_choices,
                    self._app.user_id,
                ],
                outputs=[self._graph_source_ids],
                show_progress="hidden",
            ).then(
                fn=self.persist_conversation_source_scope,
                inputs=[
                    self.chat_control.conversation_id,
                    self._app.user_id,
                    self._graph_source_ids,
                ],
                outputs=[self._graph_source_ids],
                show_progress="hidden",
            ).then(
                fn=self.refresh_chat_file_list,
                inputs=[
                    self.chat_control.conversation_id,
                    self._app.user_id,
                    self.first_selector_choices,
                    self._indices_input[1],
                    self._graph_source_ids,
                    self.chat_file_filter,
                ],
                outputs=[
                    self.chat_file_rows,
                    self.chat_file_list,
                    self.chat_selected_file,
                ],
                show_progress="hidden",
            ).then(
                fn=self.refresh_knowledge_graph,
                inputs=[
                    self.chat_control.conversation_id,
                    self._graph_source_ids,
                    self._active_file_id,
                ],
                outputs=[
                    self.plot_panel,
                    self.state_plot_panel,
                    self.knowledge_graph_status,
                    self._graph_source_ids,
                ],
                show_progress="hidden",
            )

            self.chat_control.conversation_id.change(
                fn=self.load_conversation_graph_state,
                inputs=[self.chat_control.conversation_id],
                outputs=[self._graph_source_ids],
                show_progress="hidden",
            ).then(
                fn=self.sync_graph_source_ids_with_selector_choices,
                inputs=[
                    self._graph_source_ids,
                    self.first_selector_choices,
                    self._app.user_id,
                ],
                outputs=[self._graph_source_ids],
                show_progress="hidden",
            ).then(
                fn=self.persist_conversation_source_scope,
                inputs=[
                    self.chat_control.conversation_id,
                    self._app.user_id,
                    self._graph_source_ids,
                ],
                outputs=[self._graph_source_ids],
                show_progress="hidden",
            ).then(
                fn=self.refresh_chat_file_list,
                inputs=[
                    self.chat_control.conversation_id,
                    self._app.user_id,
                    self.first_selector_choices,
                    self._indices_input[1],
                    self._graph_source_ids,
                    self.chat_file_filter,
                ],
                outputs=[
                    self.chat_file_rows,
                    self.chat_file_list,
                    self.chat_selected_file,
                ],
                show_progress="hidden",
            ).then(
                fn=self.refresh_knowledge_graph,
                inputs=[
                    self.chat_control.conversation_id,
                    self._graph_source_ids,
                    self._active_file_id,
                ],
                outputs=[
                    self.plot_panel,
                    self.state_plot_panel,
                    self.knowledge_graph_status,
                    self._graph_source_ids,
                ],
                show_progress="hidden",
            )

            if hasattr(self._app, "_tabs") and "chat-tab" in self._app._tabs:
                self._app._tabs["chat-tab"].select(
                    fn=self.sync_graph_source_ids_with_selector_choices,
                    inputs=[
                        self._graph_source_ids,
                        self.first_selector_choices,
                        self._app.user_id,
                    ],
                    outputs=[self._graph_source_ids],
                    show_progress="hidden",
                ).then(
                    fn=self.persist_conversation_source_scope,
                    inputs=[
                        self.chat_control.conversation_id,
                        self._app.user_id,
                        self._graph_source_ids,
                    ],
                    outputs=[self._graph_source_ids],
                    show_progress="hidden",
                ).then(
                    fn=self.refresh_chat_file_list,
                    inputs=[
                        self.chat_control.conversation_id,
                        self._app.user_id,
                        self.first_selector_choices,
                        self._indices_input[1],
                        self._graph_source_ids,
                        self.chat_file_filter,
                    ],
                    outputs=[
                        self.chat_file_rows,
                        self.chat_file_list,
                        self.chat_selected_file,
                    ],
                    show_progress="hidden",
                ).then(
                    fn=self.refresh_knowledge_graph,
                    inputs=[
                        self.chat_control.conversation_id,
                        self._graph_source_ids,
                        self._active_file_id,
                    ],
                    outputs=[
                        self.plot_panel,
                        self.state_plot_panel,
                        self.knowledge_graph_status,
                        self._graph_source_ids,
                    ],
                    show_progress="hidden",
                )

            self.knowledge_graph_refresh.click(
                fn=lambda: "Status: generating knowledge graph...",
                outputs=[self.knowledge_graph_status],
                show_progress="hidden",
            ).then(
                fn=self.generate_knowledge_graph,
                inputs=[
                    self.chat_control.conversation_id,
                    self._graph_source_ids,
                    self._active_file_id,
                ],
                outputs=[
                    self.plot_panel,
                    self.state_plot_panel,
                    self.knowledge_graph_status,
                    self._graph_source_ids,
                ],
                show_progress="minimal",
            )

        if KH_DEMO_MODE:
            self.paper_list.examples.select(
                self.paper_list.select_example,
                inputs=[self.paper_list.papers_state],
                outputs=[self.quick_urls],
                show_progress="hidden",
            ).then(
                lambda: (gr.update(visible=False), gr.update(visible=True)),
                outputs=[self.paper_list.accordion, self.chat_settings],
            ).then(
                fn=None,
                inputs=None,
                outputs=None,
                js=quick_urls_submit_js,
            )

    def submit_msg(
        self,
        chat_input,
        chat_history,
        user_id,
        settings,
        conv_id,
        conv_name,
        first_selector_choices,
        graph_source_ids,
        selected_page_text,
        selected_graph_context,
        request: gr.Request,
    ):
        """Submit a message to the chatbot"""
        if KH_DEMO_MODE:
            sso_user_id = check_rate_limit("chat", request)
            logger.debug("User ID: %s", sso_user_id)

        if not chat_input:
            raise ValueError("Input is empty")

        chat_input_text = chat_input.get("text", "")
        file_ids = []
        used_command = None

        first_selector_choices_map = {
            item[0]: item[1] for item in first_selector_choices
        }

        # get all file names with pattern @"filename" in input_str
        file_names, chat_input_text = get_file_names_regex(chat_input_text)

        # check if web search command is in file_names
        if WEB_SEARCH_COMMAND in file_names:
            used_command = WEB_SEARCH_COMMAND

        # get all urls in input_str
        urls, chat_input_text = get_urls(chat_input_text)

        if urls and self.first_indexing_url_fn:
            logger.debug("Detected URLs: %s", urls)
            file_ids = self.first_indexing_url_fn(
                "\n".join(urls),
                True,
                settings,
                user_id,
                request=None,
            )
        elif file_names:
            for file_name in file_names:
                file_id = first_selector_choices_map.get(file_name)
                if file_id:
                    file_ids.append(file_id)

        # add new file ids to the first selector choices
        first_selector_choices.extend(zip(urls, file_ids))
        merged_graph_source_ids = self.merge_graph_source_ids(graph_source_ids, file_ids)

        # if file_ids is not empty and chat_input_text is empty
        # set the input to summary
        if not chat_input_text and file_ids:
            chat_input_text = DEFAULT_QUESTION

        # if start of conversation and no query is specified
        if not chat_input_text and not chat_history:
            chat_input_text = DEFAULT_QUESTION

        selection_marker = "[Selected text from current page]"
        if selected_page_text and str(selected_page_text).strip():
            selected_page_text = " ".join(str(selected_page_text).split())
            if chat_input_text and selection_marker in chat_input_text:
                pass
            elif chat_input_text:
                chat_input_text = (
                    f"{chat_input_text}\n\n"
                    f"{selection_marker}\n{selected_page_text}"
                )
            else:
                chat_input_text = (
                    "Please explain the following selected text from the current page:\n"
                    f"{selected_page_text}"
                )

        if file_ids:
            selector_output = [
                "select",
                gr.update(value=file_ids, choices=first_selector_choices),
            ]
        else:
            selector_output = [gr.update(), gr.update()]

        # check if regen mode is active
        if chat_input_text:
            chat_history = chat_history + [(chat_input_text, None)]
        else:
            if not chat_history:
                raise gr.Error("Empty chat")

        if not conv_id:
            if not KH_DEMO_MODE:
                id_, update = self.chat_control.new_conv(user_id)
                with Session(engine) as session:
                    statement = select(Conversation).where(Conversation.id == id_)
                    name = session.exec(statement).one().name
                    new_conv_id = id_
                    conv_update = update
                    new_conv_name = name
            else:
                new_conv_id, new_conv_name, conv_update = None, None, gr.update()
        else:
            new_conv_id = conv_id
            conv_update = gr.update()
            new_conv_name = conv_name

        return (
            [
                {},
                chat_history,
                new_conv_id,
                conv_update,
                new_conv_name,
            ]
            + selector_output
            + [chat_input_text]
            + [used_command]
            + [selected_page_text]
            + [selected_graph_context]
            + [merged_graph_source_ids]
        )

    def get_recommendations(self, first_selector_choices, file_ids):
        first_selector_choices_map = {
            item[1]: item[0] for item in first_selector_choices
        }
        file_names = [first_selector_choices_map[file_id] for file_id in file_ids]
        if not file_names:
            return ""

        first_file_name = file_names[0].split(".")[0].replace("_", " ")
        return get_recommended_papers(first_file_name)

    def toggle_delete(self, conv_id):
        if conv_id:
            return gr.update(visible=False), gr.update(visible=True)
        else:
            return gr.update(visible=True), gr.update(visible=False)

    def on_set_public_conversation(self, is_public, convo_id):
        if not convo_id:
            gr.Warning("No conversation selected")
            return

        with Session(engine) as session:
            statement = select(Conversation).where(Conversation.id == convo_id)

            result = session.exec(statement).one()
            name = result.name

            if result.is_public != is_public:
                # Only trigger updating when user
                # select different value from the current
                result.is_public = is_public
                session.add(result)
                session.commit()

                gr.Info(
                    f"Conversation: {name} is {'public' if is_public else 'private'}."
                )

    def on_subscribe_public_events(self):
        if self.knowledge_graph and len(self._indices_input) > 1 and self.file_index:
            event_name = f"onFileIndex{self.file_index.id}Changed"
            self._app.subscribe_event(
                name=event_name,
                definition={
                    "fn": self.sync_graph_source_ids_with_selector_choices,
                    "inputs": [
                        self._graph_source_ids,
                        self.first_selector_choices,
                        self._app.user_id,
                    ],
                    "outputs": [self._graph_source_ids],
                    "show_progress": "hidden",
                },
            )
            self._app.subscribe_event(
                name=event_name,
                definition={
                    "fn": self.persist_conversation_source_scope,
                    "inputs": [
                        self.chat_control.conversation_id,
                        self._app.user_id,
                        self._graph_source_ids,
                    ],
                    "outputs": [self._graph_source_ids],
                    "show_progress": "hidden",
                },
            )
            self._app.subscribe_event(
                name=event_name,
                definition={
                    "fn": self.refresh_chat_file_list,
                    "inputs": [
                        self.chat_control.conversation_id,
                        self._app.user_id,
                        self.first_selector_choices,
                        self._indices_input[1],
                        self._graph_source_ids,
                        self.chat_file_filter,
                    ],
                    "outputs": [
                        self.chat_file_rows,
                        self.chat_file_list,
                        self.chat_selected_file,
                    ],
                    "show_progress": "hidden",
                },
            )
            self._app.subscribe_event(
                name=event_name,
                definition={
                    "fn": self.refresh_knowledge_graph,
                    "inputs": [
                        self.chat_control.conversation_id,
                        self._graph_source_ids,
                        self._active_file_id,
                    ],
                    "outputs": [
                        self.plot_panel,
                        self.state_plot_panel,
                        self.knowledge_graph_status,
                        self._graph_source_ids,
                    ],
                    "show_progress": "hidden",
                },
            )

        if self._app.f_user_management:
            self._app.subscribe_event(
                name="onSignIn",
                definition={
                    "fn": self.chat_control.reload_conv,
                    "inputs": [self._app.user_id],
                    "outputs": [self.chat_control.conversation],
                    "show_progress": "hidden",
                },
            )

            self._app.subscribe_event(
                name="onSignOut",
                definition={
                    "fn": lambda: self.chat_control.select_conv("", None),
                    "outputs": [
                        self.chat_control.conversation_id,
                        self.chat_control.conversation,
                        self.chat_control.conversation_rn,
                        self.chat_panel.chatbot,
                        self.followup_questions,
                        self.info_panel,
                        self.state_plot_panel,
                        self.state_retrieval_history,
                        self.state_plot_history,
                        self.chat_control.cb_is_public,
                        self.state_chat,
                    ]
                    + self._indices_input,
                    "show_progress": "hidden",
                },
            )

    def _on_app_created(self):
        if KH_DEMO_MODE:
            self._app.app.load(
                fn=lambda x: x,
                inputs=[self._user_api_key],
                outputs=[self._user_api_key],
                js=fetch_api_key_js,
            ).then(
                fn=self.chat_control.toggle_demo_login_visibility,
                inputs=[self._user_api_key],
                outputs=[
                    self.chat_control.cb_suggest_chat,
                    self.chat_control.btn_new,
                    self.chat_control.btn_demo_logout,
                    self.chat_control.btn_demo_login,
                ],
            ).then(
                fn=self.suggest_chat_conv,
                inputs=[
                    self._app.settings_state,
                    self.language,
                    self.chat_panel.chatbot,
                    self._use_suggestion,
                ],
                outputs=[
                    self.followup_questions_ui,
                    self.followup_questions,
                ],
            ).then(
                fn=None,
                inputs=None,
                js=chat_input_focus_js,
            )

    def persist_data_source(
        self,
        convo_id,
        user_id,
        retrieval_msg,
        plot_data,
        retrival_history,
        plot_history,
        messages,
        state,
        graph_source_ids,
        *selecteds,
    ):
        """Update the data source"""
        if not convo_id:
            gr.Warning("No conversation selected")
            return

        # if not regen, then append the new message
        if not state["app"].get("regen", False):
            retrival_history = retrival_history + [retrieval_msg]
            plot_history = plot_history + [plot_data]
        else:
            if retrival_history:
                retrival_history[-1] = retrieval_msg
                plot_history[-1] = plot_data

        # reset regen state
        state["app"]["regen"] = False

        selecteds_ = {}
        for index in self._app.index_manager.indices:
            if index.selector is None:
                continue
            if isinstance(index.selector, int):
                selecteds_[str(index.id)] = selecteds[index.selector]
            else:
                selecteds_[str(index.id)] = [selecteds[i] for i in index.selector]

        with Session(engine) as session:
            statement = select(Conversation).where(Conversation.id == convo_id)
            result = session.exec(statement).one()

            data_source = result.data_source
            old_selecteds = data_source.get("selected", {})
            is_owner = result.user == user_id

            # Write down to db
            result.data_source = {
                "selected": selecteds_ if is_owner else old_selecteds,
                "messages": messages,
                "retrieval_messages": retrival_history,
                "plot_history": plot_history,
                "state": state,
                "graph_source_ids": self._normalize_selected_file_ids(graph_source_ids),
                "likes": deepcopy(data_source.get("likes", [])),
            }
            session.add(result)
            session.commit()

        return retrival_history, plot_history

    def reasoning_changed(self, reasoning_type):
        if reasoning_type != DEFAULT_SETTING:
            # override app settings state (temporary)
            gr.Info("Reasoning type changed to `{}`".format(reasoning_type))
        return reasoning_type

    def is_liked(self, convo_id, liked: gr.LikeData):
        with Session(engine) as session:
            statement = select(Conversation).where(Conversation.id == convo_id)
            result = session.exec(statement).one()

            data_source = deepcopy(result.data_source)
            likes = data_source.get("likes", [])
            likes.append([liked.index, liked.value, liked.liked])
            data_source["likes"] = likes

            result.data_source = data_source
            session.add(result)
            session.commit()

    def message_selected(self, retrieval_history, plot_history, msg: gr.SelectData):
        index = msg.index[0]
        try:
            retrieval_content, plot_content = (
                retrieval_history[index],
                plot_history[index],
            )
        except IndexError:
            retrieval_content, plot_content = gr.update(), None

        return retrieval_content, plot_content

    @staticmethod
    def _extract_pdf_page_text(
        pdf_path: str, page_number: int, max_chars: int = 7000
    ) -> str:
        if not pdf_path or not os.path.isfile(pdf_path):
            return ""
        try:
            reader = PdfReader(pdf_path)
            if not reader.pages:
                return ""
            page_idx = max(0, min(len(reader.pages) - 1, int(page_number or 1) - 1))
            text = reader.pages[page_idx].extract_text() or ""
            text = " ".join(str(text).split())
            return text[:max_chars]
        except Exception:
            return ""

    def _get_office_page_context_text(
        self,
        active_file_id: str,
        active_file_name: str,
        page_number: int,
    ) -> str:
        page_context = self.page_preview.get_page_context_text(
            active_file_id,
            active_file_name,
            page_number,
        )
        if not page_context:
            return ""
        if os.path.isfile(page_context):
            return self._extract_pdf_page_text(page_context, page_number)
        return page_context

    def create_pipeline(
        self,
        settings: dict,
        session_reasoning_type: str,
        session_llm: str,
        session_use_mindmap: bool | str,
        session_use_citation: str,
        session_language: str,
        state: dict,
        command_state: str | None,
        user_id: int,
        active_file_id: str,
        active_file_name: str,
        page_number: int,
        selected_page_text: str,
        selected_graph_context: str,
        *selecteds,
    ):
        """Create the pipeline from settings

        Args:
            settings: the settings of the app
            state: the state of the app
            selected: the list of file ids that will be served as context. If None, then
                consider using all files

        Returns:
            - the pipeline objects
        """
        # override reasoning_mode by temporary chat page state
        reasoning_mode = (
            settings["reasoning.use"]
            if session_reasoning_type in (DEFAULT_SETTING, None)
            else session_reasoning_type
        )
        reasoning_cls = reasonings[reasoning_mode]
        reasoning_id = reasoning_cls.get_info()["id"]

        settings = deepcopy(settings)
        llm_setting_key = f"reasoning.options.{reasoning_id}.llm"
        if llm_setting_key in settings and session_llm not in (
            DEFAULT_SETTING,
            None,
            "",
        ):
            settings[llm_setting_key] = session_llm

        if session_use_mindmap not in (DEFAULT_SETTING, None):
            settings["reasoning.options.simple.create_mindmap"] = session_use_mindmap

        if session_use_citation not in (DEFAULT_SETTING, None):
            settings[
                "reasoning.options.simple.highlight_citation"
            ] = session_use_citation

        if session_language not in (DEFAULT_SETTING, None):
            settings["reasoning.lang"] = session_language

        # get retrievers
        retrievers = []

        if not active_file_name and self._app.index_manager.indices:
            first_index = self._app.index_manager.indices[0]
            selected_file_ids = []
            if isinstance(first_index.selector, tuple) and len(first_index.selector) > 1:
                selected_file_ids = selecteds[first_index.selector[1]]
            elif isinstance(first_index.selector, int):
                selected_file_ids = selecteds[first_index.selector]

            inferred_file_id, inferred_file_name, _ = self.page_preview.resolve_pdf_source(
                None, selected_file_ids
            )
            active_file_id = active_file_id or inferred_file_id
            active_file_name = inferred_file_name

        if command_state == WEB_SEARCH_COMMAND:
            # set retriever for web search
            if not WebSearch:
                raise ValueError("Web search back-end is not available.")

            web_search = WebSearch()
            retrievers.append(web_search)
        else:
            for index in self._app.index_manager.indices:
                index_selected = []
                if isinstance(index.selector, int):
                    index_selected = selecteds[index.selector]
                if isinstance(index.selector, tuple):
                    for i in index.selector:
                        index_selected.append(selecteds[i])
                iretrievers = index.get_retriever_pipelines(
                    settings, user_id, index_selected
                )
                retrievers += iretrievers

        # prepare states
        reasoning_state = {
            "app": deepcopy(state["app"]),
            "pipeline": deepcopy(state.get(reasoning_id, {})),
        }

        pipeline = reasoning_cls.get_pipeline(settings, reasoning_state, retrievers)
        normalized_page_number = max(1, int(page_number or 1))
        selected_text = (selected_page_text or "").strip()
        if (not selected_text) and active_file_id and active_file_name:
            selected_text = self._get_office_page_context_text(
                active_file_id, active_file_name, normalized_page_number
            )

        is_pdf_file = (active_file_name or "").lower().endswith(".pdf")
        pipeline.active_file_id = active_file_id or ""
        pipeline.active_file_name = active_file_name
        pipeline.page_number = normalized_page_number if is_pdf_file else None
        pipeline.selected_text = selected_text
        try:
            graph_context = (
                json.loads(selected_graph_context)
                if selected_graph_context
                else {}
            )
            if not isinstance(graph_context, dict):
                graph_context = {}
        except Exception:
            graph_context = {}
        pipeline.graph_context = graph_context

        return pipeline, reasoning_state

    def chat_fn(
        self,
        conversation_id,
        chat_history,
        settings,
        reasoning_type,
        llm_type,
        use_mind_map,
        use_citation,
        language,
        chat_state,
        command_state,
        user_id,
        active_file_id,
        active_file_name,
        page_number,
        selected_page_text,
        selected_graph_context,
        state_plot_panel,
        *selecteds,
        request: gr.Request | None = None,
    ):
        """Chat function"""
        # Extract the latest user input and any existing output
        chat_input, chat_output = chat_history[-1] if chat_history else ("", None)
        
        # Preserve the chat history excluding the latest entry which has the user input and None output
        preserved_history = chat_history[:-1] if chat_history else []

        selection_marker = "[Selected text from current page]"
        if (not selected_page_text) and isinstance(chat_input, str):
            if selection_marker in chat_input:
                selected_page_text = chat_input.split(selection_marker, 1)[1].strip()
        if isinstance(chat_input, str) and selection_marker in chat_input:
            chat_input = chat_input.split(selection_marker, 1)[0].strip()

        session_key = (
            request.session_hash
            if request is not None and request.session_hash
            else "default"
        )
        normalized_page_number = max(1, int(page_number or 1))
        page_key = make_page_key(active_file_id, normalized_page_number)
        if session_key:
            set_current_view(session_key, page_key)
        request_key = make_request_key(session_key or "default", page_key)

        init_cache_entry(
            request_key=request_key,
            session_key=session_key,
            page_key=page_key,
            file_id=active_file_id or "",
            page_number=normalized_page_number,
            last_question=str(chat_input or ""),
            preserved_history=preserved_history,
        )

        queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()

        # construct the pipeline
        pipeline, reasoning_state = self.create_pipeline(
            settings,
            reasoning_type,
            llm_type,
            use_mind_map,
            use_citation,
            language,
            chat_state,
            command_state,
            user_id,
            active_file_id,
            active_file_name,
            page_number,
            selected_page_text,
            selected_graph_context,
            *selecteds,
        )
        pipeline.set_output_queue(queue)

        text, refs, plot = "", "", state_plot_panel
        plot_gr = self._json_to_plot(state_plot_panel)
        mindmap_html = ""
        msg_placeholder = getattr(
            flowsettings, "KH_CHAT_MSG_PLACEHOLDER", "Thinking ..."
        )

        def is_active_view() -> bool:
            current_view = get_current_view(session_key) if session_key else None
            return (current_view is None) or (current_view == page_key)

        # Generate answer panel HTML with chat bubbles and thinking indicator
        answer_html = self._generate_answer_panel_html(
            preserved_history, chat_input, "", is_thinking=True
        )
        chat_history_full = preserved_history + [(chat_input, text or msg_placeholder)]

        update_answer(
            request_key,
            answer_text=text,
            answer_html=answer_html,
            chat_history=chat_history_full,
        )
        update_mindmap(request_key, mindmap_html)
        update_plot(request_key, plot)

        # Initially show the user's question with a placeholder for AI response
        active_view = is_active_view()
        yield (
            chat_history_full if active_view else gr.skip(),
            mindmap_html if active_view else gr.skip(),
            plot_gr if active_view else gr.skip(),
            plot,
            chat_state,
            answer_html if active_view else gr.skip(),
            normalized_page_number,
            active_file_id or "",
            str(chat_input or ""),
            mindmap_html,
            answer_html,
            chat_history_full,
        )

        try:
            for response in pipeline.stream(chat_input, conversation_id, preserved_history):

                if not isinstance(response, Document):
                    continue

                if response.channel is None:
                    continue

                if response.channel == "chat":
                    if response.content is None:
                        text = ""
                    else:
                        text += response.content

                if response.channel == "info":
                    if response.content is None:
                        refs = ""
                        mindmap_html = ""
                    else:
                        refs += response.content
                        if "markmap" in response.content:
                            mindmap_html += response.content

                if response.channel == "plot":
                    # Keep the knowledge graph panel stable during answer streaming.
                    plot = state_plot_panel
                    plot_gr = self._json_to_plot(state_plot_panel)

                chat_state[pipeline.get_info()["id"]] = reasoning_state["pipeline"]
                update_reasoning_state(request_key, reasoning_state["pipeline"])

                # Generate answer panel HTML with chat bubbles
                answer_html = self._generate_answer_panel_html(
                    preserved_history, chat_input, text, is_thinking=(not text)
                )
                chat_history_full = preserved_history + [
                    (chat_input, text or msg_placeholder)
                ]

                update_answer(
                    request_key,
                    answer_text=text,
                    answer_html=answer_html,
                    chat_history=chat_history_full,
                )
                update_mindmap(request_key, mindmap_html)
                update_plot(request_key, plot)

                # Update the chat history with the latest response
                active_view = is_active_view()
                yield (
                    chat_history_full if active_view else gr.skip(),
                    mindmap_html if active_view else gr.skip(),
                    plot_gr if active_view else gr.skip(),
                    plot,
                    chat_state,
                    answer_html if active_view else gr.skip(),
                    normalized_page_number,
                    active_file_id or "",
                    str(chat_input or ""),
                    mindmap_html,
                    answer_html,
                    chat_history_full,
                )
        except ValueError as e:
            logger.warning("Chat pipeline ValueError: %s", e)
            mark_error(request_key, str(e))

        if not text:
            empty_msg = getattr(
                flowsettings,
                "KH_CHAT_EMPTY_MSG_PLACEHOLDER",
                "(Sorry, I don't know)",
            )
            # Generate answer panel HTML with chat bubbles
            answer_html = self._generate_answer_panel_html(
                preserved_history, chat_input, text or empty_msg, is_thinking=False
            )
            chat_history_full = preserved_history + [(chat_input, text or empty_msg)]

            update_answer(
                request_key,
                answer_text=text or empty_msg,
                answer_html=answer_html,
                chat_history=chat_history_full,
            )
            update_mindmap(request_key, mindmap_html)
            update_plot(request_key, plot)

            active_view = is_active_view()
            yield (
                chat_history_full if active_view else gr.skip(),
                mindmap_html if active_view else gr.skip(),
                plot_gr if active_view else gr.skip(),
                plot,
                chat_state,
                answer_html if active_view else gr.skip(),
                normalized_page_number,
                active_file_id or "",
                str(chat_input or ""),
                mindmap_html,
                answer_html,
                chat_history_full,
            )

        mark_done(request_key)

    def check_and_suggest_name_conv(self, chat_history):
        suggest_pipeline = SuggestConvNamePipeline()
        new_name = gr.update()
        renamed = False

        # check if this is a newly created conversation
        if len(chat_history) == 1:
            suggested_name = suggest_pipeline(chat_history).text
            suggested_name = strip_think_tag(suggested_name)
            suggested_name = suggested_name.replace('"', "").replace("'", "")[:40]
            new_name = gr.update(value=suggested_name)
            renamed = True

        return new_name, renamed

    def suggest_chat_conv(
        self,
        settings,
        session_language,
        chat_history,
        use_suggestion,
    ):
        target_language = (
            session_language
            if session_language not in (DEFAULT_SETTING, None)
            else settings["reasoning.lang"]
        )
        if use_suggestion:
            suggest_pipeline = SuggestFollowupQuesPipeline()
            suggest_pipeline.lang = SUPPORTED_LANGUAGE_MAP.get(
                target_language, "English"
            )
            suggested_questions = [[each] for each in ChatSuggestion.CHAT_SAMPLES]

            if len(chat_history) >= 1:
                suggested_resp = suggest_pipeline(chat_history).text
                if ques_res := re.search(
                    r"\[(.*?)\]", re.sub("\n", "", suggested_resp)
                ):
                    ques_res_str = ques_res.group()
                    try:
                        suggested_questions = json.loads(ques_res_str)
                        suggested_questions = [[x] for x in suggested_questions]
                    except Exception:
                        pass

            return gr.update(visible=True), suggested_questions

        return gr.update(visible=False), gr.update()
