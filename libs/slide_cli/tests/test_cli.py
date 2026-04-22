import json

from click.testing import CliRunner

from slide_cli.cli import main


def test_help_lists_core_commands():
    runner = CliRunner()

    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0, result.output
    for token in [
        "doctor",
        "run",
        "chat",
        "sessions",
        "resume",
        "docqa",
        "ask",
        "index",
        "files",
        "docqa-sessions",
        "resume-docqa",
    ]:
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


def test_run_defaults_to_preview_mode(monkeypatch, tmp_path):
    deck_path = tmp_path / "deck.pptx"
    deck_path.write_bytes(b"placeholder")
    captured: dict[str, object] = {}

    def _fake_run_slide_task(**kwargs):
        captured.update(kwargs)
        return {
            "status": "ok",
            "mode": "preview",
            "response": "Preview ready.",
            "output_path": "",
            "patch": {"summary": "Rewrite title", "edits": []},
            "session_id": "session-2",
            "input_path": kwargs["input_path"],
            "can_apply": True,
        }

    monkeypatch.setattr("slide_cli.cli.run_slide_task", _fake_run_slide_task)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "run",
            "--file",
            str(deck_path),
            "--prompt",
            "Rewrite this deck for executives",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["apply_mode"] == "preview"


def test_run_apply_flag_sets_apply_mode(monkeypatch, tmp_path):
    deck_path = tmp_path / "deck.pptx"
    deck_path.write_bytes(b"placeholder")
    captured: dict[str, object] = {}

    def _fake_run_slide_task(**kwargs):
        captured.update(kwargs)
        return {
            "status": "ok",
            "mode": "apply",
            "response": "Applied the patch.",
            "output_path": str(tmp_path / "rewritten.pptx"),
            "patch": {"summary": "Rewrite title", "edits": []},
            "session_id": "session-3",
            "input_path": kwargs["input_path"],
            "can_apply": False,
        }

    monkeypatch.setattr("slide_cli.cli.run_slide_task", _fake_run_slide_task)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "run",
            "--file",
            str(deck_path),
            "--prompt",
            "Rewrite this deck for executives",
            "--apply",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["apply_mode"] == "apply"
