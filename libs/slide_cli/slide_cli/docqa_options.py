from __future__ import annotations

import click

TASK_TYPES = (
    "qa",
    "summary",
    "compare",
    "explain",
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
ARTIFACT_TYPES = (
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


def _source_options():
    return [
        click.option("--conversation", default="", help="Existing conversation id."),
        click.option(
            "--file",
            "file_refs",
            multiple=True,
            help="Restrict retrieval to one or more file ids or names.",
        ),
        click.option("--active-file", default="", help="Active file id or name."),
        click.option(
            "--page",
            default=None,
            type=click.IntRange(min=1),
            help="Focus QA on one page. Omit for whole-document QA.",
        ),
        click.option(
            "--scope",
            "qa_scope",
            default="auto",
            type=click.Choice(["auto", "page", "document", "multi-document"]),
            help="QA retrieval scope.",
        ),
        click.option(
            "--selected-text",
            default="",
            help="Explicit selected text to focus retrieval.",
        ),
        click.option(
            "--graph-context-file",
            default="",
            help="JSON file containing graph context to inject.",
        ),
    ]


def _mara_options():
    return [
        click.option("--reasoning", default=None, help="Temporary reasoning override."),
        click.option(
            "--task",
            "task_type",
            default=None,
            type=click.Choice(TASK_TYPES),
            help="MARA task type override.",
        ),
        click.option(
            "--agent-mode",
            default=None,
            type=click.Choice(("auto", "fast", "thorough")),
            help="MARA planning mode override.",
        ),
        click.option(
            "--artifact",
            "artifact_type",
            default=None,
            type=click.Choice(ARTIFACT_TYPES),
            help="MARA Studio artifact type to request.",
        ),
    ]


def _response_options():
    return [
        click.option(
            "--controller",
            "controller_mode",
            default="off",
            type=click.Choice(["llm", "off"]),
            show_default=True,
            help="Controller planner mode.",
        ),
        click.option(
            "--route",
            "route_policy",
            default="auto",
            type=click.Choice(
                ["auto", "direct", "doc", "visual", "element", "graph", "hybrid"]
            ),
            show_default=True,
            help="Controller route policy.",
        ),
        click.option(
            "--planner-model",
            default=None,
            help="Structured planner model override for controller auto routing.",
        ),
        click.option(
            "--allowed-route",
            "allowed_routes",
            multiple=True,
            help="Restrict controller auto routing to a route id. Repeatable.",
        ),
        click.option(
            "--verify",
            "verification_mode",
            default="off",
            type=click.Choice(["off", "light", "strict"]),
            show_default=True,
            help="Answer verification mode.",
        ),
        click.option("--llm", default=None, help="Temporary LLM override."),
        click.option(
            "--visual-retriever",
            "visual_retriever_backend",
            default=None,
            help="Visual retriever backend for visual or hybrid routes.",
        ),
        click.option(
            "--visual-generator",
            "visual_generator_backend",
            default=None,
            help="Visual generator backend for visual routes.",
        ),
        click.option(
            "--citation",
            default=None,
            type=click.Choice(["highlight", "inline", "off"]),
            help="Citation mode override.",
        ),
        click.option("--language", default=None, help="Response language override."),
        click.option(
            "--mindmap",
            flag_value=True,
            default=None,
            help="Enable mindmap output for this run.",
        ),
        click.option(
            "--json",
            "json_output",
            is_flag=True,
            default=False,
            show_default=True,
            help="Emit structured JSON output.",
        ),
    ]


def docqa_shared_options(command):
    options = [*_source_options(), *_mara_options(), *_response_options()]
    for option in reversed(options):
        command = option(command)
    return command
