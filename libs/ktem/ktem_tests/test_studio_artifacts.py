from ktem.db.models import Conversation, engine
from ktem.docqa._runtime_notebook import NOTEBOOK_KEY
from ktem.pages.chat.studio_artifacts import (
    delete_latest_artifact_update,
    export_latest_artifact_update,
    extract_mara_artifact,
    render_controller_trace_html,
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


def test_render_studio_artifacts_html_shows_saved_artifact_detail_actions():
    html = render_studio_artifacts_html(
        {
            "artifact_id": "artifact-1",
            "type": "briefing_doc",
            "title": "Launch briefing",
            "status": "ready",
            "prompt": "Create an executive briefing.",
            "source_scope": {
                "mode": "document",
                "source_ids": ["file-1"],
                "page": 3,
            },
            "payload": {
                "sections": [
                    {
                        "title": "Finding",
                        "summary": "Source-grounded launch evidence.",
                    }
                ],
                "audit_note": "Full content audit trail.",
            },
            "citations": [
                {
                    "citation_id": "c1",
                    "source_name": "launch.pdf",
                    "page_label": "3",
                }
            ],
            "exports": [{"format": "md", "path": "launch.md"}],
        }
    )

    assert "studio-artifacts-card--ready" in html
    assert "Launch briefing" in html
    assert "Create an executive briefing." in html
    assert "document" in html
    assert "file-1" in html
    assert "launch.pdf p.3" in html
    assert "launch.md" in html
    assert "Full Content" in html
    assert "Full content audit trail." in html
    assert "data-copy-text" in html
    assert "navigator.clipboard.writeText" in html
    for action in ["Copy", "Save as Note", "Export", "Delete", "Regenerate"]:
        assert action in html


def test_render_studio_artifacts_html_shows_running_and_failed_states():
    running = render_studio_artifacts_html(
        {"type": "audio_overview", "status": "running", "title": "Audio overview"}
    )
    failed = render_studio_artifacts_html(
        {
            "type": "video_overview",
            "status": "failed",
            "title": "Video overview",
            "generation": {"error": "adapter unavailable"},
        }
    )

    assert "studio-artifacts-card--running" in running
    assert "Running" in running
    assert "Audio Overview" in running
    assert "studio-artifacts-card--failed" in failed
    assert "Failed" in failed
    assert "adapter unavailable" in failed


def test_render_studio_trace_panel_keeps_trace_before_artifacts():
    html = render_studio_trace_panel(
        "<div class='reasoning-trace-card'>trace</div>",
        {"type": "study_guide", "overview": "Evidence summary"},
    )

    assert html.index("reasoning-trace-card") < html.index("studio-artifacts-card")
    assert "Evidence summary" in html


def test_render_controller_trace_html_exposes_route_verification_and_graph_evidence():
    html = render_controller_trace_html(
        route_decision={"route": "graph_global"},
        retrieve_decision={"status": "good"},
        verify_decision={
            "status": "unsupported",
            "action": "revise",
            "unsupported_claims": ["Unsupported claim."],
        },
        evidence_bundle={
            "items": [
                {
                    "modality": "graph",
                    "evidence_level": "graph",
                    "source_backrefs": ["file-a", "file-b"],
                },
                {"modality": "page_image", "evidence_level": "page"},
            ]
        },
    )

    assert "controller-trace-card" in html
    assert "Graph" in html
    assert "Verification" in html
    assert "Unsupported claim." in html
    assert "graph-level evidence" in html
    assert "Visual Page" in html


def test_render_controller_trace_html_lists_evidence_preview_and_verified_citations():
    html = render_controller_trace_html(
        route_decision={"route": "hybrid"},
        retrieve_decision={"status": "good"},
        verify_decision={
            "status": "supported",
            "action": "generate",
            "verified_citations": ["text-1", "element:file-1:4:table-a"],
        },
        evidence_bundle={
            "items": [
                {
                    "evidence_id": "text-1",
                    "modality": "text",
                    "source_name": "report.pdf",
                    "page_label": "3",
                    "text": "Revenue increased in 2026.",
                    "source_backrefs": ["file-1#page:3"],
                },
                {
                    "evidence_id": "element:file-1:4:table-a",
                    "modality": "table",
                    "source_name": "report.pdf",
                    "page_label": "4",
                    "caption": "Revenue by region",
                    "source_backrefs": ["file-1#page:4"],
                },
            ]
        },
    )

    assert "Evidence Preview" in html
    assert "report.pdf p.3" in html
    assert "Revenue increased in 2026." in html
    assert "Revenue by region" in html
    assert "Verified Citations" in html
    assert "element:file-1:4:table-a" in html


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


def test_delete_latest_artifact_update_removes_latest_artifact_and_refreshes_panel():
    conversation = Conversation(user="user-1")
    conversation.data_source = {
        NOTEBOOK_KEY: {
            "selected_source_ids": ["file-1"],
            "notes": [],
            "artifacts": [
                {
                    "artifact_id": "artifact-1",
                    "type": "study_guide",
                    "title": "Older guide",
                    "payload": {"overview": "Older."},
                },
                {
                    "artifact_id": "artifact-2",
                    "type": "briefing_doc",
                    "title": "Launch briefing",
                    "payload": {"sections": []},
                },
            ],
        }
    }
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id

    try:
        html = delete_latest_artifact_update(conversation_id)

        assert "1 saved" in html
        assert "Study Guide" in html
        with Session(engine) as session:
            row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one()
        artifacts = row.data_source[NOTEBOOK_KEY]["artifacts"]
        assert [item["artifact_id"] for item in artifacts] == ["artifact-1"]
    finally:
        with Session(engine) as session:
            cleanup_row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if cleanup_row is not None:
                session.delete(cleanup_row)
                session.commit()


def test_export_latest_artifact_update_writes_markdown_and_records_export(tmp_path):
    conversation = Conversation(user="user-1")
    conversation.data_source = {
        NOTEBOOK_KEY: {
            "selected_source_ids": ["file-1"],
            "notes": [],
            "artifacts": [
                {
                    "artifact_id": "artifact-1",
                    "type": "briefing_doc",
                    "title": "Launch briefing",
                    "payload": {"sections": [{"summary": "Grounded export."}]},
                    "exports": [],
                }
            ],
        }
    }
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id

    try:
        html = export_latest_artifact_update(conversation_id, root_dir=tmp_path)

        exported_path = tmp_path / conversation_id / "artifact-1.md"
        assert exported_path.exists()
        assert "Grounded export." in exported_path.read_text(encoding="utf-8")
        assert "artifact-1.md" in html
        with Session(engine) as session:
            row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one()
        exports = row.data_source[NOTEBOOK_KEY]["artifacts"][0]["exports"]
        assert exports[0]["format"] == "md"
        assert exports[0]["path"] == str(exported_path)
    finally:
        with Session(engine) as session:
            cleanup_row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if cleanup_row is not None:
                session.delete(cleanup_row)
                session.commit()


def test_export_latest_artifact_update_writes_selected_format_and_records_export(
    tmp_path,
):
    conversation = Conversation(user="user-1")
    conversation.data_source = {
        NOTEBOOK_KEY: {
            "selected_source_ids": ["file-1"],
            "notes": [],
            "artifacts": [
                {
                    "artifact_id": "artifact-1",
                    "type": "briefing_doc",
                    "title": "Launch briefing",
                    "payload": {"sections": [{"summary": "Grounded export."}]},
                    "exports": [],
                }
            ],
        }
    }
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id

    try:
        html = export_latest_artifact_update(
            conversation_id,
            export_format="html",
            root_dir=tmp_path,
        )

        exported_path = tmp_path / conversation_id / "artifact-1.html"
        assert exported_path.exists()
        assert "<!doctype html>" in exported_path.read_text(encoding="utf-8")
        assert "artifact-1.html" in html
        with Session(engine) as session:
            row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one()
        exports = row.data_source[NOTEBOOK_KEY]["artifacts"][0]["exports"]
        assert exports[0]["format"] == "html"
        assert exports[0]["path"] == str(exported_path)
    finally:
        with Session(engine) as session:
            cleanup_row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if cleanup_row is not None:
                session.delete(cleanup_row)
                session.commit()


def test_export_latest_artifact_update_uses_configured_media_adapter(
    monkeypatch,
    tmp_path,
):
    conversation = Conversation(user="user-1")
    conversation.data_source = {
        NOTEBOOK_KEY: {
            "selected_source_ids": ["file-1"],
            "notes": [],
            "artifacts": [
                {
                    "artifact_id": "artifact-1",
                    "type": "audio_overview",
                    "title": "Audio",
                    "payload": {"media_status": "script_only", "script": []},
                    "exports": [],
                }
            ],
        }
    }

    def media_adapter(_artifact, _export_format, output_path):
        output_path.write_bytes(b"configured-audio")
        return output_path

    monkeypatch.setattr(
        "ktem.docqa.artifact_exports.configured_media_export_adapter",
        lambda: media_adapter,
    )
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id

    try:
        html = export_latest_artifact_update(
            conversation_id,
            export_format="mp3",
            root_dir=tmp_path,
        )

        exported_path = tmp_path / conversation_id / "artifact-1.mp3"
        assert exported_path.read_bytes() == b"configured-audio"
        assert "artifact-1.mp3" in html
        with Session(engine) as session:
            row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one()
        exports = row.data_source[NOTEBOOK_KEY]["artifacts"][0]["exports"]
        assert exports[0]["format"] == "mp3"
        assert exports[0]["path"] == str(exported_path)
    finally:
        with Session(engine) as session:
            cleanup_row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if cleanup_row is not None:
                session.delete(cleanup_row)
                session.commit()
