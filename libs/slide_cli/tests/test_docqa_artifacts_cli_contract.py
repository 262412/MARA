from click.testing import CliRunner
from slide_cli.docqa_cli import docqa
from slide_cli.docqa_options import ARTIFACT_TYPES, TASK_TYPES


def test_docqa_artifact_types_cover_studio_target_catalog():
    expected = (
        "study_guide",
        "quiz",
        "flashcards",
        "mindmap",
        "slide_outline",
        "briefing_doc",
        "faq",
        "timeline",
        "custom_report",
        "data_table",
        "infographic",
        "slide_deck",
        "audio_overview",
        "video_overview",
    )

    assert ARTIFACT_TYPES == expected
    for artifact_type in expected:
        assert artifact_type in TASK_TYPES


def test_docqa_artifacts_help_exposes_crud_export_commands():
    result = CliRunner().invoke(docqa, ["artifacts", "--help"], terminal_width=300)

    assert result.exit_code == 0, result.output
    for command in [
        "generate",
        "list",
        "show",
        "export",
        "evaluate",
        "delete",
        "regenerate",
        "save-note",
    ]:
        assert command in result.output


def test_docqa_artifacts_save_note_help_exposes_artifact_option():
    result = CliRunner().invoke(
        docqa,
        ["artifacts", "save-note", "--help"],
        terminal_width=300,
    )

    assert result.exit_code == 0, result.output
    assert "--artifact" in result.output


def test_docqa_artifacts_export_help_exposes_visual_and_media_formats():
    result = CliRunner().invoke(
        docqa,
        ["artifacts", "export", "--help"],
        terminal_width=300,
    )

    assert result.exit_code == 0, result.output
    assert "[md|html|json|csv|svg|pptx|mp3|mp4]" in result.output


def test_docqa_artifacts_evaluate_help_exposes_report_options():
    result = CliRunner().invoke(
        docqa,
        ["artifacts", "evaluate", "--help"],
        terminal_width=300,
    )

    assert result.exit_code == 0, result.output
    assert "--artifact" in result.output
    assert "--output" in result.output


def test_docqa_artifacts_generate_help_exposes_studio_scope_options():
    result = CliRunner().invoke(
        docqa,
        ["artifacts", "generate", "--help"],
        terminal_width=300,
    )

    assert result.exit_code == 0, result.output
    for option in [
        "--scope",
        "--page",
        "--source",
        "--note",
        "--format",
        "--language",
        "--difficulty",
        "--count",
    ]:
        assert option in result.output
