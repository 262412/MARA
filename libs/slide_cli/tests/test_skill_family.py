from __future__ import annotations

from pathlib import Path

import click
from click.testing import CliRunner
from slide_cli.cli import main
from slide_cli.docqa_cli import docqa

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = REPO_ROOT / ".codex" / "skills"
TOP_LEVEL_COMMANDS = [
    "slide app",
    "slide doctor",
    "slide inspect",
    "slide read-slide",
    "slide extract",
    "slide search",
    "slide apply",
    "slide export-pdf",
    "slide review",
    "slide run",
    "slide chat",
    "slide sessions",
    "slide resume",
    "slide files",
    "slide read",
    "slide write",
    "slide delete",
    "slide shell",
    "slide docqa",
    "slide model",
    "slide platform",
]
TOP_LEVEL_FOCUSED_SKILLS = [
    "slide-app",
    "slide-doctor",
    "slide-inspect",
    "slide-read-slide",
    "slide-extract",
    "slide-search",
    "slide-apply",
    "slide-export-pdf",
    "slide-review",
    "slide-run",
    "slide-chat",
    "slide-sessions",
    "slide-resume",
    "slide-files",
    "slide-read",
    "slide-write",
    "slide-delete",
    "slide-shell",
    "slide-model",
    "slide-platform",
]
SLIDE_APP_SKILLS = {
    "slide-app",
    "slide-app-doctor",
    "slide-app-init",
    "slide-app-run",
}
SLIDE_MODEL_SKILLS = {
    "slide-model",
    "slide-model-init-config",
    "slide-model-providers",
    "slide-model-run",
}
SLIDE_PLATFORM_SKILLS = {
    "slide-platform",
    "slide-platform-install",
    "slide-platform-list",
    "slide-platform-status",
    "slide-platform-validate",
}
DOCQA_COMMANDS = {
    "acceptance",
    "ask",
    "chat",
    "check",
    "delete",
    "doctor",
    "files",
    "index",
    "resume",
    "sessions",
}
DOCQA_MAINLINE_COMMANDS = DOCQA_COMMANDS - {"acceptance", "check"}


def _read_skill(name: str) -> str:
    return (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")


def _command_names(group: click.Group) -> set[str]:
    with click.Context(group) as ctx:
        return set(group.list_commands(ctx))


def test_slide_cli_commands_match_top_level_skill_family():
    expected_commands = {
        command.replace("slide ", "", 1) for command in TOP_LEVEL_COMMANDS
    }
    actual_commands = _command_names(main)

    assert actual_commands == expected_commands
    assert {
        f"slide-{command}" for command in actual_commands if command != "docqa"
    } == set(TOP_LEVEL_FOCUSED_SKILLS)


def test_slide_support_groups_match_kotaemon_compat_surface():
    with click.Context(main) as ctx:
        app_group = main.get_command(ctx, "app")
        model_group = main.get_command(ctx, "model")
        platform_group = main.get_command(ctx, "platform")

    assert app_group is not None
    assert model_group is not None
    assert platform_group is not None
    assert _command_names(app_group) == {"doctor", "init", "run"}
    assert _command_names(model_group) == {"init-config", "providers", "run"}
    assert _command_names(platform_group) == {"install", "list", "status", "validate"}


def test_slide_top_level_skill_family_matches_agent_line():
    expected = {
        "slide",
        "slide-apply",
        "slide-chat",
        "slide-delete",
        "slide-doctor",
        "slide-export-pdf",
        "slide-extract",
        "slide-files",
        "slide-inspect",
        "slide-read",
        "slide-read-slide",
        "slide-resume",
        "slide-review",
        "slide-run",
        "slide-search",
        "slide-sessions",
        "slide-shell",
        "slide-write",
        *SLIDE_APP_SKILLS,
        *SLIDE_MODEL_SKILLS,
        *SLIDE_PLATFORM_SKILLS,
    }

    actual = {
        path.name
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir()
        and path.name.startswith("slide")
        and not path.name.startswith("slide-docqa")
        and (path / "SKILL.md").is_file()
    }

    assert actual == expected


def test_slide_umbrella_skill_defines_top_level_agent_line():
    skill = _read_skill("slide")

    assert "top-level slide CLI workflow" in skill

    for command in TOP_LEVEL_COMMANDS:
        assert command in skill

    for focused_skill in TOP_LEVEL_FOCUSED_SKILLS:
        assert focused_skill in skill

    for forbidden in [
        "kotaemon modelcli",
        "kotaemon platform",
    ]:
        assert forbidden not in skill


def test_slide_docqa_skill_family_matches_docqa_mainline_only():
    expected = {
        "slide-docqa",
        "slide-docqa-ask",
        "slide-docqa-chat",
        "slide-docqa-delete",
        "slide-docqa-doctor",
        "slide-docqa-files",
        "slide-docqa-index",
        "slide-docqa-resume",
        "slide-docqa-sessions",
    }

    actual = {
        path.name
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir()
        and path.name.startswith("slide-docqa")
        and (path / "SKILL.md").is_file()
    }

    assert actual == expected


def test_slide_docqa_cli_commands_match_mainline_skill_family():
    actual_commands = _command_names(docqa)

    assert actual_commands == DOCQA_COMMANDS
    assert {
        f"slide-docqa-{command}"
        for command in actual_commands
        if command in DOCQA_MAINLINE_COMMANDS
    } == {
        "slide-docqa-ask",
        "slide-docqa-chat",
        "slide-docqa-delete",
        "slide-docqa-doctor",
        "slide-docqa-files",
        "slide-docqa-index",
        "slide-docqa-resume",
        "slide-docqa-sessions",
    }
    assert "slide-docqa-acceptance" not in {
        path.name
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }
    assert "slide-docqa-check" not in {
        path.name
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }


def test_slide_docqa_umbrella_skill_stays_on_docqa_mainline():
    skill = _read_skill("slide-docqa")

    for command in [
        "slide docqa doctor",
        "slide docqa index",
        "slide docqa files",
        "slide docqa delete",
        "slide docqa sessions",
        "slide docqa ask",
        "slide docqa chat",
        "slide docqa resume",
    ]:
        assert command in skill

    for focused_skill in [
        "slide-docqa-doctor",
        "slide-docqa-index",
        "slide-docqa-files",
        "slide-docqa-delete",
        "slide-docqa-sessions",
        "slide-docqa-ask",
        "slide-docqa-chat",
        "slide-docqa-resume",
    ]:
        assert focused_skill in skill

    for forbidden in [
        "kotaemon app init",
        "kotaemon app doctor",
        "kotaemon modelcli",
        "kotaemon platform",
    ]:
        assert forbidden not in skill


def test_docqa_help_marks_acceptance_as_maintainer_command():
    runner = CliRunner()
    result = runner.invoke(docqa, ["--help"])

    assert result.exit_code == 0, result.output
    assert "Maintainer acceptance check" in result.output
