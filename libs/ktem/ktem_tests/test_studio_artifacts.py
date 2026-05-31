from ktem.db.models import Conversation, engine
from ktem.docqa._runtime_notebook import NOTEBOOK_KEY
from ktem.pages.chat.studio_artifacts import (
    extract_mara_artifact,
    render_conversation_notebook_panel_html,
    render_notebook_panel_html,
    render_studio_artifacts_html,
    render_studio_trace_panel,
)
from sqlmodel import Session, select

from kotaemon.base import Document


def test_extract_mara_artifact_reads_debug_payload():
    response = Document(
        channel="debug",
        content={
            "mara_channel": "artifact",
            "payload": {"type": "quiz", "multiple_choice": []},
        },
    )

    assert extract_mara_artifact(response) == {
        "type": "quiz",
        "multiple_choice": [],
    }


def test_render_studio_artifacts_html_lists_supported_empty_state():
    html = render_studio_artifacts_html()

    assert "studio-artifacts-card studio-artifacts-card--empty" in html
    assert "Study Guide" in html
    assert "Quiz" in html
    assert "Flashcards" in html
    assert "Mind Map" in html
    assert "Slide Outline" in html


def test_render_studio_artifacts_html_summarizes_generated_artifact():
    html = render_studio_artifacts_html(
        {
            "type": "slide_outline",
            "title": "Source-grounded MARA outline",
            "sections": [
                {
                    "title": "Evidence-backed narrative",
                    "slides": [
                        {
                            "title": "paper.pdf p.3",
                            "bullets": ["Grounded bullet"],
                        }
                    ],
                }
            ],
            "cited_evidence": [{"file_name": "paper.pdf", "page_label": "3"}],
        }
    )

    assert "studio-artifacts-card--ready" in html
    assert "Slide Outline" in html
    assert "Source-grounded MARA outline" in html
    assert "paper.pdf p.3" in html
    assert "Grounded bullet" in html


def test_render_studio_trace_panel_keeps_trace_before_artifacts():
    html = render_studio_trace_panel(
        "<div class='reasoning-trace-card'>trace</div>",
        {"type": "study_guide", "overview": "Evidence summary"},
    )

    assert html.index("reasoning-trace-card") < html.index("studio-artifacts-card")
    assert "Evidence summary" in html


def test_render_notebook_panel_html_exposes_source_notes_and_artifact_access():
    html = render_notebook_panel_html(
        {
            "selected_source_ids": ["file-1", "file-2"],
            "notes": [{"title": "Grounding note"}],
            "artifacts": [{"type": "quiz"}],
        }
    )

    assert "notebook-panel-card" in html
    assert "Sources" in html
    assert "Source Guide" in html
    assert "Notes" in html
    assert "Grounding note" in html
    assert "Artifacts" in html
    assert "Quiz" in html


def test_render_conversation_notebook_panel_html_reads_saved_notebook_state():
    conversation = Conversation(user="user-1")
    conversation.data_source = {
        NOTEBOOK_KEY: {
            "selected_source_ids": ["file-1"],
            "notes": [{"title": "Saved answer", "text": "Grounded note"}],
            "artifacts": [{"type": "study_guide", "payload": {}}],
        }
    }
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id

    try:
        html = render_conversation_notebook_panel_html(conversation_id)

        assert "1 selected" in html
        assert "Saved answer" in html
        assert "Study Guide" in html
    finally:
        with Session(engine) as session:
            cleanup_row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if cleanup_row is not None:
                session.delete(cleanup_row)
                session.commit()
