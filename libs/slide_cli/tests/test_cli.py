import json

from click.testing import CliRunner

from slide_cli.cli import main


def test_help_lists_core_commands():
    runner = CliRunner()

    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0, result.output
    for token in ["doctor", "run", "chat", "sessions", "resume"]:
        assert token in result.output


def test_doctor_json(monkeypatch):
    payload = {
        "ok": True,
        "config_path": "C:/tmp/modelcli.yml",
        "providers": {"openai": {"available": False, "reason": "missing API key"}},
        "python_pptx": True,
        "libreoffice": False,
    }
    monkeypatch.setattr("slide_cli.cli._collect_doctor_payload", lambda: payload)

    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--json"])

    assert result.exit_code == 0, result.output
    decoded = json.loads(result.output)
    assert decoded["ok"] is True
    assert decoded["python_pptx"] is True
    assert decoded["providers"]["openai"]["reason"] == "missing API key"


def test_run_dry_run_json(monkeypatch, tmp_path):
    deck_path = tmp_path / "deck.pptx"
    deck_path.write_bytes(b"placeholder")

    monkeypatch.setattr(
        "slide_cli.cli.run_slide_task",
        lambda **kwargs: {
            "status": "ok",
            "mode": "dry-run",
            "response": "Suggested edits prepared.",
            "output_path": "",
            "patch": {"summary": "Rewrite title", "edits": []},
            "session_id": "session-1",
            "input_path": kwargs["input_path"],
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "run",
            "--file",
            str(deck_path),
            "--prompt",
            "Rewrite this deck for executives",
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    decoded = json.loads(result.output)
    assert decoded["status"] == "ok"
    assert decoded["mode"] == "dry-run"
    assert decoded["session_id"] == "session-1"
    assert decoded["input_path"] == str(deck_path)
