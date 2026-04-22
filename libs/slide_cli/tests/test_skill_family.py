from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from slide_cli.docqa_cli import docqa


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = REPO_ROOT / ".codex" / "skills"


def _read_skill(name: str) -> str:
    return (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")


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
