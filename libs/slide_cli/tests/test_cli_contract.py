import json
import sys
import types
from pathlib import Path

from click.testing import CliRunner
from slide_cli.cli import main


def _listed_commands(help_output: str) -> set[str]:
    commands: set[str] = set()
    in_commands = False
    for raw_line in help_output.splitlines():
        line = raw_line.rstrip()
        if line.startswith("Commands:"):
            in_commands = True
            continue
        if not in_commands:
            continue
        if not line.strip():
            break
        stripped = line.strip()
        if stripped:
            commands.add(stripped.split()[0])
    return commands


def _install_trogon_stub(monkeypatch):
    trogon = types.ModuleType("trogon")

    def tui(*_args, **_kwargs):
        def decorator(command):
            return command

        return decorator

    setattr(trogon, "tui", tui)
    monkeypatch.setitem(sys.modules, "trogon", trogon)
    monkeypatch.delitem(sys.modules, "kotaemon.cli", raising=False)


def test_public_entry_points_expose_only_mara_commands():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")

    assert 'name = "mara-research-cli"' in text
    assert 'name = "slide-cli"' not in text
    assert 'MARA = "slide_cli.cli:main"' in text
    assert 'MARA-cli = "slide_cli.cli:main"' in text
    assert 'slide = "slide_cli.cli:main"' not in text
    assert 'slide-cli = "slide_cli.cli:main"' not in text


def test_public_runtime_paths_use_mara_app_name():
    paths_module = Path(__file__).resolve().parents[1] / "slide_cli" / "paths.py"
    text = paths_module.read_text(encoding="utf-8")

    assert 'DEFAULT_APP_NAME = "MARA"' in text
    assert 'DEFAULT_APP_NAME = "mara-research-cli"' not in text


def test_public_agent_prompt_uses_mara_brand():
    agent_module = Path(__file__).resolve().parents[1] / "slide_cli" / "agent.py"
    text = agent_module.read_text(encoding="utf-8")

    assert "You are MARA's top-level agent line." in text
    assert "You are Slide CLI" not in text


def test_public_mara_help_keeps_canonical_command_surface():
    runner = CliRunner()

    result = runner.invoke(main, ["--help"], prog_name="MARA", terminal_width=300)

    assert result.exit_code == 0, result.output
    assert "Unified MARA product CLI." in result.output
    assert _listed_commands(result.output) == {
        "app",
        "apply",
        "chat",
        "delete",
        "docqa",
        "doctor",
        "export-pdf",
        "extract",
        "files",
        "inspect",
        "model",
        "platform",
        "read",
        "read-slide",
        "resume",
        "review",
        "run",
        "search",
        "sessions",
        "shell",
        "write",
    }


def test_public_doctor_help_and_json_contract(monkeypatch):
    payload = {
        "ok": True,
        "config_path": "C:/tmp/modelcli.yml",
        "providers": {"openai": {"available": False, "reason": "missing API key"}},
        "python_pptx": True,
        "libreoffice": False,
    }
    monkeypatch.setattr("slide_cli.cli._collect_doctor_payload", lambda: payload)
    runner = CliRunner()

    help_result = runner.invoke(main, ["doctor", "--help"])
    json_result = runner.invoke(main, ["doctor", "--json"])

    assert help_result.exit_code == 0, help_result.output
    assert "Validate the top-level MARA agent runtime" in help_result.output
    assert "--json" in help_result.output
    assert "Emit structured JSON output." in help_result.output

    assert json_result.exit_code == 0, json_result.output
    decoded = json.loads(json_result.output)
    assert decoded == payload


def test_public_docqa_group_help_is_available_from_mara_entry():
    runner = CliRunner()

    result = runner.invoke(
        main, ["docqa", "--help"], prog_name="MARA", terminal_width=300
    )

    assert result.exit_code == 0, result.output
    assert (
        "Document QA CLI backed by the app's runtime/index/session data."
        in result.output
    )
    assert "Action guide:" in result.output
    assert _listed_commands(result.output) == {
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


def test_public_docqa_ask_help_is_available_from_mara_entry():
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["docqa", "ask", "--help"],
        prog_name="MARA",
        terminal_width=300,
    )

    assert result.exit_code == 0, result.output
    for token in [
        "--prompt",
        "--conversation",
        "--file",
        "--active-file",
        "--page",
        "--scope",
        "--selected-text",
        "--graph-context-file",
        "--reasoning",
        "--llm",
        "--citation",
        "--language",
        "--mindmap",
        "--json",
        'MARA docqa ask --file report.pdf --prompt "Summarize this document"',
        'MARA docqa ask --file report.pdf --page 12 --prompt "What does this page say?"',
        (
            "MARA docqa ask --file report.pdf --selected-text "
            '"contract termination clause" --prompt "Explain this section"'
        ),
    ]:
        assert token in result.output


def test_public_support_group_help_contracts(monkeypatch):
    _install_trogon_stub(monkeypatch)
    runner = CliRunner()
    expectations = {
        "app": (
            "Packaged app setup, doctor, and launch workflows.",
            {"doctor", "init", "run"},
        ),
        "model": (
            "Shared model routing workflows.",
            {"init-config", "providers", "run"},
        ),
        "platform": (
            "Install and validate Codex and Claude Code support assets.",
            {"install", "list", "status", "validate"},
        ),
    }

    for group_name, (summary, commands) in expectations.items():
        result = runner.invoke(main, [group_name, "--help"], terminal_width=300)

        assert result.exit_code == 0, result.output
        assert summary in result.output
        assert _listed_commands(result.output) == commands
