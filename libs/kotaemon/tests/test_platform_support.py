import json
from pathlib import Path

from click.testing import CliRunner

from kotaemon.cli import main
from kotaemon.platform_support import (
    install_platform,
    list_platform_names,
    validate_bundle,
    validate_installed,
)


def test_platform_registry_names():
    assert set(list_platform_names()) == {"claude-code", "codex"}


def test_install_claude_minimal_creates_expected_assets(tmp_path):
    result = install_platform(
        platform_name="claude-code",
        mode="minimal",
        target_dir=tmp_path,
    )

    assert result.platform == "claude-code"
    assert (tmp_path / "skills").exists()
    assert (tmp_path / "agents").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "skills" / "kotaemon-docqa" / "SKILL.md").exists()


def test_install_claude_settings_template_merges_existing_json(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"existing": 1, "hooks": {}}\n', encoding="utf-8")

    result = install_platform(
        platform_name="claude-code",
        mode="selective",
        items=["settings.json.template"],
        target_dir=tmp_path,
    )

    merged = json.loads(settings_path.read_text(encoding="utf-8"))
    assert merged["existing"] == 1
    assert "customInstructions" in merged
    assert "hooks" in merged
    assert (tmp_path / "settings.kotaemon.template.json").exists()
    assert str(settings_path) in result.merged_paths


def test_install_codex_agents_uses_sidecar_when_existing_file_present(tmp_path):
    primary = tmp_path / "AGENTS.md"
    primary.write_text("user owned content\n", encoding="utf-8")

    result = install_platform(
        platform_name="codex",
        mode="selective",
        items=["AGENTS.md"],
        target_dir=tmp_path,
    )

    sidecar = tmp_path / "AGENTS.kotaemon.md"
    assert primary.read_text(encoding="utf-8") == "user owned content\n"
    assert sidecar.exists()
    assert str(sidecar) in result.sidecar_paths


def test_install_codex_minimal_includes_docqa_skill(tmp_path):
    result = install_platform(
        platform_name="codex",
        mode="minimal",
        target_dir=tmp_path,
    )

    assert result.platform == "codex"
    assert (tmp_path / "skills" / "kotaemon-docqa" / "SKILL.md").exists()


def test_install_claude_selective_commands_include_docqa_wrapper(tmp_path):
    result = install_platform(
        platform_name="claude-code",
        mode="selective",
        items=["commands"],
        target_dir=tmp_path,
    )

    assert result.platform == "claude-code"
    assert (tmp_path / "commands" / "kotaemon-docqa.md").exists()


def test_validate_bundle_passes_for_packaged_assets():
    results = validate_bundle()
    assert results
    assert all(item.valid for item in results), [
        (item.platform, item.errors) for item in results
    ]


def test_validate_installed_reports_missing_minimal_components(tmp_path):
    result = validate_installed("codex", target_dir=tmp_path)
    assert result.valid is False
    assert any(
        message.startswith("Missing minimal component") for message in result.errors
    )


def test_cli_platform_list_command():
    runner = CliRunner()
    result = runner.invoke(main, ["platform", "list"])

    assert result.exit_code == 0, result.output
    assert "claude-code" in result.output
    assert "codex" in result.output


def test_cli_platform_install_dry_run(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "platform",
            "install",
            "--platform",
            "codex",
            "--mode",
            "minimal",
            "--target-dir",
            str(tmp_path),
            "--dry-run",
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Dry run: yes" in result.output
    assert (tmp_path / "skills").exists() is False


def test_cli_platform_validate_bundle_command():
    runner = CliRunner()
    result = runner.invoke(main, ["platform", "validate", "--platform", "codex"])

    assert result.exit_code == 0, result.output
    assert "codex: PASS" in result.output


def test_docqa_skill_parity_between_platforms():
    repo_root = Path(__file__).resolve().parents[3]
    codex_skill = (
        repo_root
        / "libs"
        / "kotaemon"
        / "kotaemon"
        / "platform_support"
        / "assets"
        / "codex"
        / "skills"
        / "kotaemon-docqa"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    claude_skill = (
        repo_root
        / "libs"
        / "kotaemon"
        / "kotaemon"
        / "platform_support"
        / "assets"
        / "claude-code"
        / "skills"
        / "kotaemon-docqa"
        / "SKILL.md"
    ).read_text(encoding="utf-8")

    shared_tokens = [
        "kotaemon docqa doctor",
        "kotaemon docqa index <path...> [--reindex]",
        "kotaemon docqa files",
        "kotaemon docqa delete <file-id-or-name>...",
        "kotaemon docqa ask --prompt \"...\"",
        "kotaemon docqa chat",
        "kotaemon docqa sessions",
        "kotaemon docqa resume <conversation-id>",
        "kotaemon docqa acceptance",
        "--conversation <conversation-id>",
        "--file <file-id-or-name>",
        "--active-file <file-id-or-name>",
        "--page <n>",
        "--selected-text \"...\"",
        "--graph-context-file <path.json>",
        "--reasoning <reasoning-id>",
        "--llm <llm-name>",
        "--citation highlight|inline|off",
        "--language <language>",
        "--mindmap",
        "--json",
        "--keep-artifacts",
        "--verbose",
    ]

    for token in shared_tokens:
        assert token in codex_skill
        assert token in claude_skill


def test_cli_operations_skill_parity_between_platforms():
    repo_root = Path(__file__).resolve().parents[3]
    codex_skill = (
        repo_root
        / "libs"
        / "kotaemon"
        / "kotaemon"
        / "platform_support"
        / "assets"
        / "codex"
        / "skills"
        / "kotaemon-cli-operations"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    claude_skill = (
        repo_root
        / "libs"
        / "kotaemon"
        / "kotaemon"
        / "platform_support"
        / "assets"
        / "claude-code"
        / "skills"
        / "kotaemon-cli-operations"
        / "SKILL.md"
    ).read_text(encoding="utf-8")

    shared_tokens = [
        "kotaemon modelcli init-config --output modelcli.yml",
        "kotaemon modelcli providers --config modelcli.yml",
        "kotaemon modelcli run --prompt \"...\" --model ds-chat --provider openai --config modelcli.yml --dry-run",
        "kotaemon modelcli run --prompt \"...\" --model ds-chat --provider openai --config modelcli.yml",
        "kotaemon promptui run promptui.yml --port 7860",
        "python -m benchmark run --manifest benchmark/manifests/format_robustness.json --suite-name smoke",
    ]

    for token in shared_tokens:
        assert token in codex_skill
        assert token in claude_skill
