from __future__ import annotations

from typing import Any

import gradio as gr

from .studio_artifact_generation import STUDIO_ARTIFACT_TYPE_CHOICES
from .studio_artifact_parameters import artifact_parameter_state
from .studio_artifact_picker import (
    render_studio_artifact_detail_header,
    render_studio_artifact_picker,
)
from .studio_note_controls import render_studio_note_controls

STUDIO_EXPORT_FORMAT_CHOICES = (
    "md",
    "html",
    "json",
    "csv",
    "svg",
    "pptx",
    "mp3",
    "mp4",
)


def render_studio_artifact_controls(page: Any) -> None:
    render_studio_artifact_picker(page)
    initial_parameters = artifact_parameter_state("study_guide")
    with gr.Column(
        visible=False,
        elem_id="studio-artifact-detail-panel",
        elem_classes=["studio-artifact-detail-panel"],
    ) as page.studio_artifact_detail_panel:
        render_studio_artifact_detail_header(page)
        _render_studio_artifact_type(page)
        _render_primary_fields(page, initial_parameters)
        _render_parameter_row(page, initial_parameters)
        _render_format_explanation(page, initial_parameters)
        page.studio_generate_artifact_button = gr.Button(
            "Generate Artifact",
            variant="primary",
            elem_id="studio-generate-artifact",
        )
    _render_studio_artifact_actions(page)


def _render_studio_artifact_type(page: Any) -> None:
    page.studio_artifact_type = gr.Dropdown(
        choices=list(STUDIO_ARTIFACT_TYPE_CHOICES),
        value="study_guide",
        label="Artifact",
        visible=False,
        container=False,
        elem_id="studio-artifact-type",
    )


def _render_primary_fields(
    page: Any,
    initial_parameters: dict[str, dict[str, Any]],
) -> None:
    page.studio_artifact_scope = gr.Dropdown(
        choices=["page", "document", "multi-document"],
        value="page",
        label="Source scope",
        container=True,
        elem_id="studio-artifact-scope",
        elem_classes=["studio-artifact-field"],
    )
    page.studio_artifact_prompt = gr.Textbox(
        value="",
        lines=3,
        label=initial_parameters["prompt"]["label"],
        placeholder=initial_parameters["prompt"]["placeholder"],
        visible=initial_parameters["prompt"]["visible"],
        container=True,
        elem_id="studio-artifact-prompt",
        elem_classes=["studio-artifact-field"],
    )
    page.studio_artifact_note_ids = gr.Textbox(
        value="",
        label="Note IDs",
        visible=False,
        container=False,
        elem_id="studio-artifact-note-ids",
        elem_classes=["studio-artifact-field"],
    )


def _render_parameter_row(
    page: Any,
    initial_parameters: dict[str, dict[str, Any]],
) -> None:
    with gr.Row(
        elem_id="studio-artifact-parameter-row",
        elem_classes=["studio-artifact-parameter-row"],
    ):
        _render_dropdown(page, "format", initial_parameters["format"])
        _render_dropdown(page, "difficulty", initial_parameters["difficulty"])
        _render_dropdown(page, "count", initial_parameters["count"])


def _render_dropdown(
    page: Any,
    name: str,
    field: dict[str, Any],
) -> None:
    setattr(
        page,
        f"studio_artifact_{name}",
        gr.Dropdown(
            choices=list(field["choices"]),
            value=field["value"],
            label=field["label"],
            visible=field["visible"],
            container=True,
            elem_id=f"studio-artifact-{name}",
            elem_classes=["studio-artifact-field"],
        ),
    )


def _render_format_explanation(
    page: Any,
    initial_parameters: dict[str, dict[str, Any]],
) -> None:
    page.studio_artifact_format_explanation = gr.Markdown(
        value=initial_parameters["format_explanation"]["value"],
        visible=initial_parameters["format_explanation"]["visible"],
        elem_id="studio-artifact-format-explanation",
        elem_classes=["studio-artifact-field"],
    )


def _render_studio_artifact_actions(page: Any) -> None:
    render_studio_note_controls(page)
    with gr.Row():
        page.studio_delete_artifact_button = gr.Button(
            "Delete Latest Artifact",
            variant="secondary",
            elem_id="studio-delete-latest-artifact",
        )
    with gr.Row():
        page.studio_export_format = gr.Dropdown(
            choices=list(STUDIO_EXPORT_FORMAT_CHOICES),
            value="md",
            label="Export",
            container=False,
            elem_id="studio-export-format",
        )
        page.studio_export_artifact_button = gr.Button(
            "Export Latest Artifact",
            variant="secondary",
            elem_id="studio-export-latest-artifact",
        )
    page.studio_regenerate_artifact_button = gr.Button(
        "Regenerate Latest Artifact",
        variant="secondary",
        elem_id="studio-regenerate-latest-artifact",
    )
