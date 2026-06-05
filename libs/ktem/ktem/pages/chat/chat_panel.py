"""Chat panel component for displaying chatbot and document preview.

Provides the main chat interface with integrated PDF/document preview and page navigation.
"""

import gradio as gr
from ktem.app import BasePage
from theflow.settings import settings as flowsettings

KH_DEMO_MODE = getattr(flowsettings, "KH_DEMO_MODE", False)

# Placeholder text shown in chatbot based on mode
if not KH_DEMO_MODE:
    PLACEHOLDER_TEXT = (
        "This is the beginning of a new conversation.\n"
        "Start by uploading a file or a web URL. "
        "Visit Files tab for more document-management options."
    )
else:
    PLACEHOLDER_TEXT = (
        "Welcome to MARA Demo. "
        "Start by browsing preloaded conversations to get onboard.\n"
        "Check out Hint section for more tips."
    )


class ChatPanel(BasePage):
    """Main chat panel with integrated document preview."""

    def __init__(self, app):
        self._app = app
        self.text_input = None
        self.qa_scope = None
        self.on_building_ui()

    def on_building_ui(self):
        """Build the chat panel UI components."""
        self.render_preview_frame()

    def render_preview_frame(self):
        """Render the hidden chat history and central page preview frame."""
        # Chatbot for displaying conversations
        self.chatbot = gr.Chatbot(
            label=self._app.app_name,
            placeholder=PLACEHOLDER_TEXT,
            show_label=False,
            elem_id="main-chat-bot",
            show_copy_button=True,
            likeable=True,
            bubble_full_width=False,
            visible=False,
            latex_delimiters=[
                {"left": "$$", "right": "$$", "display": True},
                {"left": "$", "right": "$", "display": False},
                {"left": "\\(", "right": "\\)", "display": False},
                {"left": "\\[", "right": "\\]", "display": True},
            ],
        )

        # HTML-based PDF/document preview panel
        self.pdf_preview = gr.HTML(
            value=(
                "<div class='pdf-preview-shell'>"
                "<iframe id='main-pdf-preview-frame' title='PDF Preview' loading='lazy'></iframe>"
                "<img id='main-pdf-preview-image' class='pdf-preview-image' alt='PDF page preview' />"
                "<div id='main-pdf-preview-empty' class='pdf-preview-empty pdf-preview-empty--prototype'>"
                "<div class='preview-empty-state'>Select a file and page to preview.</div>"
                "</div>"
                "</div>"
            ),
            elem_id="main-pdf-preview",
        )
        # Hidden textbox storing the preview source URL
        self.pdf_preview_src = gr.Textbox(
            value="", visible=False, elem_id="main-pdf-preview-src"
        )
        # Keep timer available for explicit preview polling without starting
        # a background Gradio queue loop as soon as the app loads.
        self.preview_refresh_timer = gr.Timer(value=2.0, active=False)

    def render_notice_and_pager(self):
        """Render PDF preview notice message and page navigation controls."""
        # Notice message shown above PDF preview
        self.pdf_preview_notice = gr.HTML(
            value="<div class='pdf-preview-notice'>Selected page preview.</div>",
            elem_id="pdf-preview-notice",
        )

        # Page navigation row with previous/next buttons and page number input
        with gr.Row(equal_height=True, elem_id="pdf-pager-row"):
            self.prev_page_btn = gr.Button("◀ Prev", scale=1, min_width=80)
            self.page_number = gr.Number(
                value=1,
                precision=0,
                minimum=1,
                scale=1,
                min_width=100,
                container=False,
                show_label=False,
                elem_id="pdf-page-number",
            )
            self.next_page_btn = gr.Button("Next ▶", scale=1, min_width=80)

    def render_input(self):
        """Render the chat input box with multimodal support."""
        with gr.Row(elem_id="chat-input-row"):
            self.qa_scope = gr.Radio(
                choices=[
                    ("Page", "page"),
                    ("Document", "document"),
                    ("Multi-doc", "multi_document"),
                ],
                value="page",
                container=False,
                show_label=False,
                scale=4,
                min_width=220,
                elem_id="qa-scope",
            )
            # Multimodal input supporting text and file uploads
            self.text_input = gr.MultimodalTextbox(
                interactive=True,
                scale=16,
                file_count="multiple",
                placeholder="Ask a question about the selected page",
                container=False,
                show_label=False,
                elem_id="chat-input",
            )

    def submit_msg(self, chat_input, chat_history):
        """Submit a message to the chatbot.

        Args:
            chat_input: User's input message
            chat_history: Current chat history

        Returns:
            Tuple of (empty string for clearing input, updated chat history)
        """
        return "", chat_history + [(chat_input, None)]
