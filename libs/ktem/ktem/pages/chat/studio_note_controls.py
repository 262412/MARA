from __future__ import annotations

from functools import partial
from typing import Any

import gradio as gr

from .studio_note_actions import (
    convert_note_to_source_update,
    save_latest_answer_note_update,
    save_latest_artifact_note_update,
    save_manual_note_update,
)


def render_studio_note_controls(page: Any) -> None:
    with gr.Accordion(
        label="Studio Notes",
        open=False,
        elem_id="studio-notes-panel",
    ):
        page.studio_manual_note_title = gr.Textbox(
            value="",
            label="Title",
            container=False,
            elem_id="studio-manual-note-title",
        )
        page.studio_manual_note_text = gr.Textbox(
            value="",
            lines=3,
            label="Note",
            container=False,
            elem_id="studio-manual-note-text",
        )
        page.studio_save_manual_note_button = gr.Button(
            "Save Note",
            variant="secondary",
            elem_id="studio-save-manual-note",
        )
        page.studio_convert_note_id = gr.Textbox(
            value="",
            label="Note ID",
            container=False,
            elem_id="studio-convert-note-id",
        )
        page.studio_convert_note_source_button = gr.Button(
            "Convert Note to Source",
            variant="secondary",
            elem_id="studio-convert-note-source",
        )
    with gr.Row():
        page.studio_save_answer_note_button = gr.Button(
            "Save Latest Answer as Note",
            variant="secondary",
            elem_id="studio-save-latest-answer-note",
        )
        page.studio_save_note_button = gr.Button(
            "Save Latest Artifact as Note",
            variant="secondary",
            elem_id="studio-save-latest-artifact-note",
        )


def bind_studio_note_events(page: Any) -> None:
    page.studio_save_answer_note_button.click(
        save_latest_answer_note_update,
        inputs=[
            page.chat_control.conversation_id,
            page.chat_panel.chatbot,
            page.state_retrieval_history,
        ],
        outputs=[page.notebook_panel],
        show_progress="hidden",
    )
    page.studio_save_note_button.click(
        save_latest_artifact_note_update,
        inputs=[page.chat_control.conversation_id],
        outputs=[page.notebook_panel],
        show_progress="hidden",
    )
    page.studio_save_manual_note_button.click(
        save_manual_note_update,
        inputs=[
            page.chat_control.conversation_id,
            page.studio_manual_note_title,
            page.studio_manual_note_text,
        ],
        outputs=[page.notebook_panel],
        show_progress="hidden",
    )
    page.studio_convert_note_source_button.click(
        partial(convert_note_to_source_update, page.docqa),
        inputs=[page.chat_control.conversation_id, page.studio_convert_note_id],
        outputs=[page.notebook_panel],
        show_progress="hidden",
    )
