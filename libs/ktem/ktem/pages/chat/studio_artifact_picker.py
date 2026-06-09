from __future__ import annotations

from functools import partial
from typing import Any

import gradio as gr
from ktem.docqa.artifact_models import ARTIFACT_LABELS

from .studio_artifact_generation import STUDIO_ARTIFACT_TYPE_CHOICES

_CARD_DESCRIPTIONS = {
    "audio_overview": "Narrated source overview",
    "video_overview": "Scripted video outline",
    "briefing_doc": "Executive report",
    "quiz": "Custom assessment",
    "data_table": "Structured table",
    "slide_outline": "Presentation draft",
    "mindmap": "Concept map",
    "flashcards": "Study cards",
    "infographic": "Visual summary",
    "study_guide": "Guided notes",
    "faq": "Question set",
    "timeline": "Chronology",
    "custom_report": "Source-grounded report",
    "slide_deck": "Deck plan",
}


def render_studio_artifact_picker(page: Any) -> None:
    page.studio_artifact_card_buttons = {}
    with gr.Column(
        elem_id="studio-artifact-selector-panel",
        elem_classes=["studio-artifact-selector-panel"],
    ) as page.studio_artifact_selector_panel:
        gr.HTML(_selector_header_html(), elem_id="studio-artifact-selector-header")
        with gr.Column(
            elem_id="studio-artifact-card-grid",
            elem_classes=["studio-artifact-card-grid"],
        ):
            for row in _card_rows(STUDIO_ARTIFACT_TYPE_CHOICES):
                with gr.Row(elem_classes=["studio-artifact-card-row"]):
                    for artifact_type in row:
                        page.studio_artifact_card_buttons[artifact_type] = gr.Button(
                            _card_button_label(artifact_type),
                            variant="secondary",
                            elem_id=f"studio-artifact-card-{_artifact_slug(artifact_type)}",
                            elem_classes=["studio-artifact-card-button"],
                        )
    page.studio_artifact_overlay_backdrop = gr.HTML(
        "<div class='studio-artifact-overlay-backdrop__veil' aria-hidden='true'></div>",
        visible=False,
        elem_id="studio-artifact-overlay-backdrop",
        elem_classes=["studio-artifact-overlay-backdrop"],
    )


def render_studio_artifact_detail_header(page: Any) -> None:
    with gr.Row(elem_id="studio-artifact-detail-header"):
        page.studio_artifact_detail_title = gr.HTML(
            _detail_title_html("study_guide"),
            elem_id="studio-artifact-detail-title",
        )
        page.studio_artifact_detail_back_button = gr.Button(
            "Close",
            variant="secondary",
            elem_id="studio-artifact-detail-back",
        )


def bind_studio_artifact_picker_events(page: Any) -> None:
    for artifact_type, button in page.studio_artifact_card_buttons.items():
        button.click(
            partial(select_studio_artifact_type_update, artifact_type),
            inputs=[],
            outputs=studio_artifact_selection_outputs(page),
            show_progress="hidden",
        )
    page.studio_artifact_detail_back_button.click(
        show_studio_artifact_picker_update,
        inputs=[],
        outputs=studio_artifact_visibility_outputs(page),
        show_progress="hidden",
    )


def studio_artifact_selection_outputs(page: Any) -> list[Any]:
    return [
        page.studio_artifact_type,
        page.studio_artifact_selector_panel,
        page.studio_artifact_overlay_backdrop,
        page.studio_artifact_detail_panel,
        page.studio_artifact_detail_title,
    ]


def studio_artifact_visibility_outputs(page: Any) -> list[Any]:
    return [
        page.studio_artifact_selector_panel,
        page.studio_artifact_overlay_backdrop,
        page.studio_artifact_detail_panel,
    ]


def select_studio_artifact_type_update(artifact_type: str) -> tuple[Any, ...]:
    selected = str(artifact_type or "study_guide").strip() or "study_guide"
    return (
        selected,
        gr.update(visible=True),
        gr.update(visible=True),
        gr.update(visible=True),
        _detail_title_html(selected),
    )


def show_studio_artifact_picker_update() -> tuple[Any, ...]:
    return gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)


def _card_rows(artifact_types: tuple[str, ...]) -> list[tuple[str, ...]]:
    return [
        tuple(artifact_types[index : index + 2])
        for index in range(0, len(artifact_types), 2)
    ]


def _card_button_label(artifact_type: str) -> str:
    label = ARTIFACT_LABELS.get(artifact_type, artifact_type.replace("_", " ").title())
    description = _CARD_DESCRIPTIONS.get(artifact_type, "Source artifact")
    return f"{label}\n{description} >"


def _detail_title_html(artifact_type: str) -> str:
    label = ARTIFACT_LABELS.get(artifact_type, artifact_type.replace("_", " ").title())
    return (
        "<div class='studio-artifact-detail-title'>"
        f"<strong>{label}</strong>"
        "<span>Configure prompt, scope, notes, and output parameters.</span>"
        "</div>"
    )


def _selector_header_html() -> str:
    return (
        "<div class='studio-artifact-selector-title'>"
        "<strong>Studio</strong>"
        "<span>Select an artifact type to configure generation.</span>"
        "</div>"
    )


def _artifact_slug(artifact_type: str) -> str:
    return str(artifact_type or "").strip().replace("_", "-")
