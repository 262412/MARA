from pathlib import Path

CHAT_PAGE_FILE = (
    Path(__file__).resolve().parents[1] / "ktem" / "pages" / "chat" / "__init__.py"
)
STUDIO_CONTROLS_FILE = (
    Path(__file__).resolve().parents[1]
    / "ktem"
    / "pages"
    / "chat"
    / "studio_artifact_controls.py"
)
STUDIO_NOTE_CONTROLS_FILE = (
    Path(__file__).resolve().parents[1]
    / "ktem"
    / "pages"
    / "chat"
    / "studio_note_controls.py"
)
STUDIO_RENDERING_FILE = (
    Path(__file__).resolve().parents[1]
    / "ktem"
    / "pages"
    / "chat"
    / "studio_artifact_control_rendering.py"
)
STUDIO_PICKER_FILE = (
    Path(__file__).resolve().parents[1]
    / "ktem"
    / "pages"
    / "chat"
    / "studio_artifact_picker.py"
)


def _read_chat_page() -> str:
    return CHAT_PAGE_FILE.read_text(encoding="utf-8")


def _read_studio_controls() -> str:
    return STUDIO_CONTROLS_FILE.read_text(encoding="utf-8")


def _read_studio_rendering() -> str:
    return STUDIO_RENDERING_FILE.read_text(encoding="utf-8")


def _read_studio_control_sources() -> str:
    sources = [_read_studio_controls(), _read_studio_rendering()]
    if STUDIO_PICKER_FILE.exists():
        sources.append(STUDIO_PICKER_FILE.read_text(encoding="utf-8"))
    if STUDIO_NOTE_CONTROLS_FILE.exists():
        sources.append(STUDIO_NOTE_CONTROLS_FILE.read_text(encoding="utf-8"))
    return "\n".join(sources)


def test_chat_page_exposes_studio_generate_controls():
    chat_page = _read_chat_page()
    controls = _read_studio_control_sources()

    assert "render_studio_artifact_controls(self)" in chat_page
    assert 'elem_id="studio-artifact-selector-panel"' in controls
    assert 'elem_id="studio-artifact-overlay-backdrop"' in controls
    assert 'elem_id="studio-artifact-detail-panel"' in controls
    assert "studio-artifact-card-" in controls
    assert "_artifact_slug(artifact_type)" in controls
    assert 'elem_id="studio-artifact-detail-back"' in controls
    assert 'elem_id="studio-artifact-type"' in controls
    assert 'elem_id="studio-artifact-scope"' in controls
    assert 'elem_id="studio-artifact-prompt"' in controls
    assert 'elem_id="studio-artifact-note-ids"' in controls
    assert 'elem_id="studio-generate-artifact"' in controls


def test_chat_page_exposes_labeled_studio_artifact_detail_fields():
    controls = _read_studio_rendering()

    assert 'label="Source scope"' in controls
    assert 'label=initial_parameters["prompt"]["label"]' in controls
    assert 'label=field["label"]' in controls
    assert 'choices=list(field["choices"])' in controls
    assert 'visible=field["visible"]' in controls
    assert 'elem_id="studio-artifact-format-explanation"' in controls
    assert '_render_dropdown(page, "count", initial_parameters["count"])' in controls
    assert "page.studio_artifact_count = gr.Number" not in controls
    assert 'label="Item count"' not in controls
    assert 'elem_id="studio-artifact-parameter-row"' in controls
    assert 'elem_classes=["studio-artifact-field"]' in controls
    assert "container=True" in controls


def test_chat_page_binds_studio_generate_after_notebook_refresh():
    chat_page = _read_chat_page()
    controls = _read_studio_control_sources()

    assert chat_page.index(
        "self.chat_control.conversation_id.change"
    ) < chat_page.index("bind_studio_artifact_events(self)")
    assert "bind_studio_artifact_picker_events(page)" in controls
    assert "select_studio_artifact_type_update" in controls
    assert "studio_artifact_selection_outputs(page)" in controls
    assert "page.studio_artifact_overlay_backdrop" in controls
    assert "page.studio_artifact_detail_back_button.click" in controls
    assert "page.studio_artifact_format.change" in controls
    assert "update_studio_artifact_dependent_parameters" in controls
    assert "page.studio_generate_artifact_button.click" in controls
    assert "render_studio_artifact_running_update" in controls
    assert (
        "outputs=[\n"
        "            page.reasoning_trace_panel,\n"
        "            page.plot_panel,\n"
        "            page.studio_artifact_selector_panel,\n"
        "            page.studio_artifact_overlay_backdrop,\n"
        "            page.studio_artifact_detail_panel,\n"
        "        ]" in controls
    )
    assert (
        "inputs=[\n"
        "            page.studio_artifact_type,\n"
        "            page._graph_source_ids,\n"
        "            page._active_file_id,\n"
        "            *page._indices_input,\n"
        "        ]" in controls
    )
    assert ".then(\n        partial(generate_studio_artifact_panel_update" in controls
    assert "generate_studio_artifact_panel_update" in controls
    assert "inputs=studio_generate_inputs(page)" in controls
    assert "outputs=studio_generate_outputs(page)" in controls


def test_chat_page_exposes_studio_save_note_button():
    chat_page = _read_chat_page()

    controls = _read_studio_control_sources()

    assert "bind_studio_artifact_events(self)" in chat_page
    assert "save_latest_answer_note_update" in controls
    assert 'elem_id="studio-save-latest-answer-note"' in controls
    assert "save_latest_artifact_note_update" in controls
    assert 'elem_id="studio-save-latest-artifact-note"' in controls
    assert "save_manual_note_update" in controls
    assert 'elem_id="studio-manual-note-title"' in controls
    assert 'elem_id="studio-manual-note-text"' in controls
    assert 'elem_id="studio-save-manual-note"' in controls
    assert "convert_note_to_source_update" in controls
    assert 'elem_id="studio-convert-note-id"' in controls
    assert 'elem_id="studio-convert-note-source"' in controls
    assert "delete_latest_artifact_update" in controls
    assert 'elem_id="studio-delete-latest-artifact"' in controls
    assert "export_latest_artifact_update" in controls
    assert 'elem_id="studio-export-latest-artifact"' in controls
    assert 'elem_id="studio-export-format"' in controls
    assert '"mp3"' in controls
    assert '"mp4"' in controls
    assert "regenerate_latest_studio_artifact_panel_update" in controls
    assert 'elem_id="studio-regenerate-latest-artifact"' in controls


def test_chat_page_binds_studio_save_note_without_moving_notebook_refresh():
    chat_page = _read_chat_page()
    controls = _read_studio_control_sources()

    assert chat_page.index(
        "self.chat_control.conversation_id.change"
    ) < chat_page.index("bind_studio_artifact_events(self)")
    assert ".click(\n        save_latest_answer_note_update" in controls
    assert "page.state_retrieval_history" in controls
    assert ".click(\n        save_latest_artifact_note_update" in controls
    assert ".click(\n        save_manual_note_update" in controls
    assert ".click(\n        partial(convert_note_to_source_update" in controls
    assert "outputs=[page.notebook_panel]" in controls


def test_chat_page_binds_studio_delete_without_moving_notebook_refresh():
    chat_page = _read_chat_page()
    controls = _read_studio_control_sources()

    assert chat_page.index(
        "self.chat_control.conversation_id.change"
    ) < chat_page.index("bind_studio_artifact_events(self)")
    assert ".click(\n        delete_latest_artifact_update" in controls
    assert "outputs=[page.notebook_panel]" in controls


def test_chat_page_binds_studio_export_without_moving_notebook_refresh():
    chat_page = _read_chat_page()
    controls = _read_studio_control_sources()

    assert chat_page.index(
        "self.chat_control.conversation_id.change"
    ) < chat_page.index("bind_studio_artifact_events(self)")
    assert ".click(\n        export_latest_artifact_update" in controls
    assert (
        "inputs=[page.chat_control.conversation_id, page.studio_export_format]"
        in controls
    )
    assert "outputs=[page.notebook_panel]" in controls


def test_chat_page_binds_studio_regenerate_without_moving_notebook_refresh():
    chat_page = _read_chat_page()
    controls = _read_studio_controls()

    assert chat_page.index(
        "self.chat_control.conversation_id.change"
    ) < chat_page.index("bind_studio_artifact_events(self)")
    assert "page.studio_regenerate_artifact_button.click" in controls
    assert "render_studio_artifact_regenerating_update" in controls
    assert "inputs=[page.chat_control.conversation_id]" in controls
    assert "regenerate_latest_studio_artifact_panel_update" in controls
    assert (
        ".then(\n        partial(regenerate_latest_studio_artifact_panel_update"
        in controls
    )
    assert "inputs=studio_regenerate_inputs(page)" in controls
    assert "outputs=studio_generate_outputs(page)" in controls
