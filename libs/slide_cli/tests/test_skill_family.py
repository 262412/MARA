from __future__ import annotations

from pathlib import Path

import click
from click.testing import CliRunner
from slide_cli.cli import main
from slide_cli.docqa_cli import docqa

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = REPO_ROOT / ".codex" / "skills"
TOP_LEVEL_COMMANDS = [
    "MARA app",
    "MARA doctor",
    "MARA inspect",
    "MARA read-slide",
    "MARA extract",
    "MARA search",
    "MARA apply",
    "MARA export-pdf",
    "MARA review",
    "MARA run",
    "MARA chat",
    "MARA sessions",
    "MARA resume",
    "MARA files",
    "MARA read",
    "MARA write",
    "MARA delete",
    "MARA shell",
    "MARA docqa",
    "MARA model",
    "MARA platform",
]
TOP_LEVEL_FOCUSED_SKILLS = [
    "MARA-app",
    "MARA-doctor",
    "MARA-inspect",
    "MARA-read-slide",
    "MARA-extract",
    "MARA-search",
    "MARA-apply",
    "MARA-export-pdf",
    "MARA-review",
    "MARA-run",
    "MARA-chat",
    "MARA-sessions",
    "MARA-resume",
    "MARA-files",
    "MARA-read",
    "MARA-write",
    "MARA-delete",
    "MARA-shell",
    "MARA-model",
    "MARA-platform",
]
MARA_APP_SKILLS = {
    "MARA-app",
    "MARA-app-doctor",
    "MARA-app-init",
    "MARA-app-run",
}
MARA_MODEL_SKILLS = {
    "MARA-model",
    "MARA-model-init-config",
    "MARA-model-providers",
    "MARA-model-run",
}
MARA_PLATFORM_SKILLS = {
    "MARA-platform",
    "MARA-platform-install",
    "MARA-platform-list",
    "MARA-platform-status",
    "MARA-platform-validate",
}
DOCQA_COMMANDS = {
    "acceptance",
    "artifacts",
    "ask",
    "chat",
    "check",
    "delete",
    "doctor",
    "files",
    "index",
    "notes",
    "resume",
    "sessions",
    "sources",
}
DOCQA_MAINLINE_COMMANDS = DOCQA_COMMANDS - {"acceptance", "check"}


def _read_skill(name: str) -> str:
    return (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")


def _command_names(group: click.Group) -> set[str]:
    with click.Context(group) as ctx:
        return set(group.list_commands(ctx))


def test_mara_cli_commands_match_top_level_skill_family():
    expected_commands = {
        command.replace("MARA ", "", 1) for command in TOP_LEVEL_COMMANDS
    }
    actual_commands = _command_names(main)

    assert actual_commands == expected_commands
    assert {
        f"MARA-{command}" for command in actual_commands if command != "docqa"
    } == set(TOP_LEVEL_FOCUSED_SKILLS)


def test_mara_support_groups_match_kotaemon_compat_surface():
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


def test_mara_top_level_skill_family_matches_agent_line():
    expected = {
        "MARA",
        "MARA-apply",
        "MARA-chat",
        "MARA-delete",
        "MARA-doctor",
        "MARA-export-pdf",
        "MARA-extract",
        "MARA-files",
        "MARA-inspect",
        "MARA-read",
        "MARA-read-slide",
        "MARA-resume",
        "MARA-review",
        "MARA-run",
        "MARA-search",
        "MARA-sessions",
        "MARA-shell",
        "MARA-write",
        *MARA_APP_SKILLS,
        *MARA_MODEL_SKILLS,
        *MARA_PLATFORM_SKILLS,
    }

    actual = {
        path.name
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir()
        and path.name.startswith("MARA")
        and not path.name.startswith("MARA-docqa")
        and (path / "SKILL.md").is_file()
    }

    assert actual == expected


def test_mara_umbrella_skill_defines_top_level_agent_line():
    skill = _read_skill("MARA")

    assert "top-level MARA CLI workflow" in skill

    for command in TOP_LEVEL_COMMANDS:
        assert command in skill

    for focused_skill in TOP_LEVEL_FOCUSED_SKILLS:
        assert focused_skill in skill

    for forbidden in [
        "kotaemon modelcli",
        "kotaemon platform",
    ]:
        assert forbidden not in skill


def test_mara_docqa_skill_family_matches_docqa_mainline_only():
    expected = {
        "MARA-docqa",
        "MARA-docqa-artifacts",
        "MARA-docqa-ask",
        "MARA-docqa-chat",
        "MARA-docqa-delete",
        "MARA-docqa-doctor",
        "MARA-docqa-files",
        "MARA-docqa-index",
        "MARA-docqa-notes",
        "MARA-docqa-resume",
        "MARA-docqa-sessions",
        "MARA-docqa-sources",
    }

    actual = {
        path.name
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir()
        and path.name.startswith("MARA-docqa")
        and (path / "SKILL.md").is_file()
    }

    assert actual == expected


def test_mara_docqa_cli_commands_match_mainline_skill_family():
    actual_commands = _command_names(docqa)

    assert actual_commands == DOCQA_COMMANDS
    assert {
        f"MARA-docqa-{command}"
        for command in actual_commands
        if command in DOCQA_MAINLINE_COMMANDS
    } == {
        "MARA-docqa-artifacts",
        "MARA-docqa-ask",
        "MARA-docqa-chat",
        "MARA-docqa-delete",
        "MARA-docqa-doctor",
        "MARA-docqa-files",
        "MARA-docqa-index",
        "MARA-docqa-notes",
        "MARA-docqa-resume",
        "MARA-docqa-sessions",
        "MARA-docqa-sources",
    }
    assert "MARA-docqa-acceptance" not in {
        path.name
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }
    assert "MARA-docqa-check" not in {
        path.name
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }


def test_mara_docqa_umbrella_skill_stays_on_docqa_mainline():
    skill = _read_skill("MARA-docqa")

    for command in [
        "MARA docqa doctor",
        "MARA docqa index",
        "MARA docqa files",
        "MARA docqa delete",
        "MARA docqa sessions",
        "MARA docqa notes",
        "MARA docqa sources",
        "MARA docqa artifacts",
        "MARA docqa ask",
        "MARA docqa chat",
        "MARA docqa resume",
    ]:
        assert command in skill

    for focused_skill in [
        "MARA-docqa-doctor",
        "MARA-docqa-index",
        "MARA-docqa-files",
        "MARA-docqa-delete",
        "MARA-docqa-sessions",
        "MARA-docqa-notes",
        "MARA-docqa-sources",
        "MARA-docqa-artifacts",
        "MARA-docqa-ask",
        "MARA-docqa-chat",
        "MARA-docqa-resume",
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
