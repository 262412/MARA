import json
from pathlib import Path

import click
from click.testing import CliRunner

from kotaemon.cli import main, platform, promptui
from kotaemon.platform_support import (
    install_platform,
    list_platform_names,
    validate_bundle,
    validate_installed,
)
from kotaemon.platform_support import validator as platform_validator

DOCQA_ACTION_SKILLS = (
    "kotaemon-docqa-ask",
    "kotaemon-docqa-index",
    "kotaemon-docqa-chat",
    "kotaemon-docqa-files",
    "kotaemon-docqa-delete",
    "kotaemon-docqa-sessions",
    "kotaemon-docqa-resume",
    "kotaemon-docqa-doctor",
    "kotaemon-docqa-acceptance",
)
MODELCLI_ACTION_SKILLS = (
    "kotaemon-modelcli-init-config",
    "kotaemon-modelcli-providers",
    "kotaemon-modelcli-run",
)
APP_ACTION_SKILLS = (
    "kotaemon-app-init",
    "kotaemon-app-doctor",
    "kotaemon-app-run",
)
PLATFORM_ACTION_SKILLS = (
    "kotaemon-platform-install",
    "kotaemon-platform-list",
    "kotaemon-platform-status",
    "kotaemon-platform-validate",
)
SLIDE_ACTION_SKILLS = (
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
)
SLIDE_DOCQA_ACTION_SKILLS = (
    "slide-docqa-ask",
    "slide-docqa-chat",
    "slide-docqa-delete",
    "slide-docqa-doctor",
    "slide-docqa-files",
    "slide-docqa-index",
    "slide-docqa-resume",
    "slide-docqa-sessions",
)
CANONICAL_PROJECT_SKILLS = {
    "kotaemon-app",
    "kotaemon-cli-operations",
    "kotaemon-docqa",
    "kotaemon-modelcli",
    "kotaemon-platform",
    "slide",
    "slide-docqa",
    *APP_ACTION_SKILLS,
    *DOCQA_ACTION_SKILLS,
    *MODELCLI_ACTION_SKILLS,
    *PLATFORM_ACTION_SKILLS,
    *SLIDE_ACTION_SKILLS,
    *SLIDE_DOCQA_ACTION_SKILLS,
}


def _skill_names(root: Path) -> set[str]:
    return {
        path.name
        for path in root.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }


def _claude_command_names(root: Path) -> set[str]:
    return {path.stem for path in root.glob("*.md") if path.is_file()}


def _platform_assets_root(platform_name: str) -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "libs"
        / "kotaemon"
        / "kotaemon"
        / "platform_support"
        / "assets"
        / platform_name
    )


def _command_names(group: click.Group) -> set[str]:
    with click.Context(group) as ctx:
        return set(group.list_commands(ctx))


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
    for skill_name in DOCQA_ACTION_SKILLS:
        assert (tmp_path / "skills" / skill_name / "SKILL.md").exists()
    assert (tmp_path / "skills" / "kotaemon-modelcli" / "SKILL.md").exists()
    assert (tmp_path / "skills" / "kotaemon-app" / "SKILL.md").exists()
    assert (tmp_path / "skills" / "kotaemon-platform" / "SKILL.md").exists()
    for skill_name in MODELCLI_ACTION_SKILLS + APP_ACTION_SKILLS:
        assert (tmp_path / "skills" / skill_name / "SKILL.md").exists()
    for skill_name in PLATFORM_ACTION_SKILLS:
        assert (tmp_path / "skills" / skill_name / "SKILL.md").exists()
    assert (tmp_path / "skills" / "slide" / "SKILL.md").exists()
    assert (tmp_path / "skills" / "slide-docqa" / "SKILL.md").exists()
    for skill_name in SLIDE_ACTION_SKILLS + SLIDE_DOCQA_ACTION_SKILLS:
        assert (tmp_path / "skills" / skill_name / "SKILL.md").exists()


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
    for skill_name in DOCQA_ACTION_SKILLS:
        assert (tmp_path / "skills" / skill_name / "SKILL.md").exists()
    assert (tmp_path / "skills" / "kotaemon-modelcli" / "SKILL.md").exists()
    assert (tmp_path / "skills" / "kotaemon-app" / "SKILL.md").exists()
    assert (tmp_path / "skills" / "kotaemon-platform" / "SKILL.md").exists()
    for skill_name in MODELCLI_ACTION_SKILLS + APP_ACTION_SKILLS:
        assert (tmp_path / "skills" / skill_name / "SKILL.md").exists()
    for skill_name in PLATFORM_ACTION_SKILLS:
        assert (tmp_path / "skills" / skill_name / "SKILL.md").exists()
    assert (tmp_path / "skills" / "slide" / "SKILL.md").exists()
    assert (tmp_path / "skills" / "slide-docqa" / "SKILL.md").exists()
    for skill_name in SLIDE_ACTION_SKILLS + SLIDE_DOCQA_ACTION_SKILLS:
        assert (tmp_path / "skills" / skill_name / "SKILL.md").exists()


def test_install_claude_selective_commands_include_docqa_wrapper(tmp_path):
    result = install_platform(
        platform_name="claude-code",
        mode="selective",
        items=["commands"],
        target_dir=tmp_path,
    )

    assert result.platform == "claude-code"
    assert (tmp_path / "commands" / "kotaemon-docqa.md").exists()
    for skill_name in DOCQA_ACTION_SKILLS:
        assert (tmp_path / "commands" / f"{skill_name}.md").exists()
    assert (tmp_path / "commands" / "kotaemon-modelcli.md").exists()
    assert (tmp_path / "commands" / "kotaemon-app.md").exists()
    assert (tmp_path / "commands" / "kotaemon-cli-operations.md").exists()
    assert (tmp_path / "commands" / "kotaemon-platform.md").exists()
    for skill_name in MODELCLI_ACTION_SKILLS + APP_ACTION_SKILLS:
        assert (tmp_path / "commands" / f"{skill_name}.md").exists()
    for skill_name in PLATFORM_ACTION_SKILLS:
        assert (tmp_path / "commands" / f"{skill_name}.md").exists()
    assert (tmp_path / "commands" / "slide.md").exists()
    assert (tmp_path / "commands" / "slide-docqa.md").exists()
    for skill_name in SLIDE_ACTION_SKILLS + SLIDE_DOCQA_ACTION_SKILLS:
        assert (tmp_path / "commands" / f"{skill_name}.md").exists()


def test_validate_bundle_passes_for_packaged_assets():
    results = validate_bundle()
    assert results
    assert all(item.valid for item in results), [
        (item.platform, item.errors) for item in results
    ]


def test_platform_skill_surfaces_are_exactly_unified():
    repo_root = Path(__file__).resolve().parents[3]
    root_codex_skills = repo_root / ".codex" / "skills"
    packaged_codex_skills = _platform_assets_root("codex") / "skills"
    packaged_claude_skills = _platform_assets_root("claude-code") / "skills"

    assert _skill_names(root_codex_skills) == CANONICAL_PROJECT_SKILLS
    assert _skill_names(packaged_codex_skills) == CANONICAL_PROJECT_SKILLS
    assert _skill_names(packaged_claude_skills) == CANONICAL_PROJECT_SKILLS

    for skill_name in CANONICAL_PROJECT_SKILLS:
        root_text = (root_codex_skills / skill_name / "SKILL.md").read_text(
            encoding="utf-8"
        )
        codex_text = (packaged_codex_skills / skill_name / "SKILL.md").read_text(
            encoding="utf-8"
        )
        claude_text = (packaged_claude_skills / skill_name / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert root_text == codex_text
        assert root_text == claude_text


def test_claude_commands_are_exactly_unified_with_skills():
    command_names = _claude_command_names(
        _platform_assets_root("claude-code") / "commands"
    )

    assert command_names == CANONICAL_PROJECT_SKILLS


def test_validate_bundle_reports_missing_split_docqa_asset(monkeypatch, tmp_path):
    skills_dir = tmp_path / "skills"
    commands_dir = tmp_path / "commands"
    agents_dir = tmp_path / "agents"
    utils_dir = tmp_path / "utils"
    scripts_dir = tmp_path / "scripts"

    for path in (skills_dir, commands_dir, agents_dir, utils_dir, scripts_dir):
        path.mkdir(parents=True, exist_ok=True)

    (tmp_path / "AGENTS.md").write_text("profile\n", encoding="utf-8")
    (tmp_path / "config.toml.template").write_text(
        "# BEGIN KOTAEMON PLATFORM BLOCK\n", encoding="utf-8"
    )
    for skill_name in (
        "kotaemon-docqa",
        "kotaemon-modelcli",
        "kotaemon-app",
        "kotaemon-platform",
    ):
        (skills_dir / skill_name).mkdir()
        (skills_dir / skill_name / "SKILL.md").write_text(
            "umbrella\n", encoding="utf-8"
        )

    class _Spec:
        selectable_components = (
            "skills",
            "agents",
            "utils",
            "scripts",
            "AGENTS.md",
            "config.toml.template",
        )
        bundle_root = tmp_path

    monkeypatch.setattr(platform_validator, "get_platform_spec", lambda _: _Spec())
    monkeypatch.setattr(platform_validator, "list_platform_names", lambda: ["codex"])

    result = validate_bundle("codex")[0]

    assert result.valid is False
    assert any("kotaemon-docqa-ask" in error for error in result.errors)


def test_validate_installed_reports_missing_minimal_components(tmp_path):
    result = validate_installed("codex", target_dir=tmp_path)
    assert result.valid is False
    assert any(
        message.startswith("Missing minimal component") for message in result.errors
    )


def test_validate_installed_passes_after_minimal_install(tmp_path):
    for platform_name in ("codex", "claude-code"):
        target_dir = tmp_path / platform_name
        install_platform(
            platform_name=platform_name,
            mode="minimal",
            target_dir=target_dir,
        )

        result = validate_installed(platform_name, target_dir=target_dir)

        assert result.valid is True, (platform_name, result.errors)


def test_validate_installed_passes_after_full_install(tmp_path):
    for platform_name in ("codex", "claude-code"):
        target_dir = tmp_path / platform_name
        install_platform(
            platform_name=platform_name,
            mode="full",
            target_dir=target_dir,
        )

        result = validate_installed(platform_name, target_dir=target_dir)

        assert result.valid is True, (platform_name, result.errors)


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


def test_kotaemon_platform_cli_commands_match_skill_family():
    actual_commands = _command_names(platform)

    assert actual_commands == {"install", "list", "status", "validate"}
    assert {f"kotaemon-platform-{command}" for command in actual_commands} == set(
        PLATFORM_ACTION_SKILLS
    )


def test_kotaemon_misc_cli_commands_are_covered_by_operations_skill():
    repo_root = Path(__file__).resolve().parents[3]
    operations_skill = (
        repo_root / ".codex" / "skills" / "kotaemon-cli-operations" / "SKILL.md"
    ).read_text(encoding="utf-8")

    assert {"promptui", "makedoc", "start-project", "ui"} <= _command_names(main)
    assert _command_names(promptui) == {"export", "run"}

    for token in [
        "kotaemon promptui export <pipeline-path> --output promptui.yml",
        "kotaemon promptui run promptui.yml --port 7860",
        "kotaemon makedoc <module> --output docs.md",
        "kotaemon start-project --template project-default",
        "kotaemon ui",
    ]:
        assert token in operations_skill


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
        "pip install kotaemon-app",
        "uv tool install kotaemon-app",
        "kotaemon app init",
        "kotaemon app doctor",
        "kotaemon docqa doctor",
        "kotaemon docqa index <path...> [--reindex]",
        "kotaemon docqa files",
        "kotaemon docqa delete <file-id-or-name>...",
        'kotaemon docqa ask --prompt "..."',
        "kotaemon docqa chat",
        "kotaemon docqa sessions",
        "kotaemon docqa resume <conversation-id>",
        "kotaemon docqa acceptance",
        "--conversation <conversation-id>",
        "--file <file-id-or-name>",
        "--active-file <file-id-or-name>",
        "--page <n>",
        '--selected-text "..."',
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


def test_modelcli_skill_parity_between_platforms():
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
        / "kotaemon-modelcli"
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
        / "kotaemon-modelcli"
        / "SKILL.md"
    ).read_text(encoding="utf-8")

    shared_tokens = [
        "pip install kotaemon-app",
        "uv tool install kotaemon-app",
        "kotaemon app init",
        "kotaemon app doctor",
        "kotaemon modelcli init-config --output modelcli.yml",
        "kotaemon modelcli providers --config modelcli.yml",
        'kotaemon modelcli run --prompt "..." --model ds-chat --provider openai --config modelcli.yml --dry-run',
        'kotaemon modelcli run --prompt "..." --model ds-chat --provider openai --config modelcli.yml',
    ]

    for token in shared_tokens:
        assert token in codex_skill
        assert token in claude_skill


def test_app_skill_parity_between_platforms():
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
        / "kotaemon-app"
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
        / "kotaemon-app"
        / "SKILL.md"
    ).read_text(encoding="utf-8")

    shared_tokens = [
        "pip install kotaemon-app",
        "uv tool install kotaemon-app",
        "kotaemon app init",
        "kotaemon app doctor",
        "kotaemon app run",
    ]

    for token in shared_tokens:
        assert token in codex_skill
        assert token in claude_skill


def test_platform_skill_parity_between_platforms():
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
        / "kotaemon-platform"
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
        / "kotaemon-platform"
        / "SKILL.md"
    ).read_text(encoding="utf-8")

    shared_tokens = [
        "kotaemon platform list",
        "kotaemon platform status --platform codex",
        "kotaemon platform install --platform codex --mode full --yes",
        "kotaemon platform install --platform claude-code --mode full --yes",
        "kotaemon platform validate",
        "kotaemon platform validate --platform codex --installed",
    ]

    for token in shared_tokens:
        assert token in codex_skill
        assert token in claude_skill


def test_split_docqa_action_skills_match_between_platforms():
    repo_root = Path(__file__).resolve().parents[3]
    shared_tokens = [
        "pip install kotaemon-app",
        "uv tool install kotaemon-app",
        "kotaemon app init",
        "kotaemon app doctor",
    ]

    for skill_name in DOCQA_ACTION_SKILLS:
        codex_skill = (
            repo_root
            / "libs"
            / "kotaemon"
            / "kotaemon"
            / "platform_support"
            / "assets"
            / "codex"
            / "skills"
            / skill_name
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
            / skill_name
            / "SKILL.md"
        ).read_text(encoding="utf-8")

        for token in shared_tokens:
            assert token in codex_skill
            assert token in claude_skill


def test_split_modelcli_action_skills_match_between_platforms():
    repo_root = Path(__file__).resolve().parents[3]
    shared_tokens = [
        "pip install kotaemon-app",
        "uv tool install kotaemon-app",
        "kotaemon app init",
        "kotaemon app doctor",
    ]

    for skill_name in MODELCLI_ACTION_SKILLS:
        codex_skill = (
            repo_root
            / "libs"
            / "kotaemon"
            / "kotaemon"
            / "platform_support"
            / "assets"
            / "codex"
            / "skills"
            / skill_name
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
            / skill_name
            / "SKILL.md"
        ).read_text(encoding="utf-8")

        for token in shared_tokens:
            assert token in codex_skill
            assert token in claude_skill


def test_split_app_action_skills_match_between_platforms():
    repo_root = Path(__file__).resolve().parents[3]
    shared_tokens = [
        "pip install kotaemon-app",
        "uv tool install kotaemon-app",
        "kotaemon app init",
        "kotaemon app doctor",
    ]

    for skill_name in APP_ACTION_SKILLS:
        codex_skill = (
            repo_root
            / "libs"
            / "kotaemon"
            / "kotaemon"
            / "platform_support"
            / "assets"
            / "codex"
            / "skills"
            / skill_name
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
            / skill_name
            / "SKILL.md"
        ).read_text(encoding="utf-8")

        for token in shared_tokens:
            assert token in codex_skill
            assert token in claude_skill


def test_split_platform_action_skills_match_between_platforms():
    repo_root = Path(__file__).resolve().parents[3]
    shared_tokens = [
        "kotaemon platform",
    ]

    for skill_name in PLATFORM_ACTION_SKILLS:
        codex_skill = (
            repo_root
            / "libs"
            / "kotaemon"
            / "kotaemon"
            / "platform_support"
            / "assets"
            / "codex"
            / "skills"
            / skill_name
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
            / skill_name
            / "SKILL.md"
        ).read_text(encoding="utf-8")

        for token in shared_tokens:
            assert token in codex_skill
            assert token in claude_skill


def test_claude_docqa_action_commands_match_skill_names():
    repo_root = Path(__file__).resolve().parents[3]
    commands_dir = (
        repo_root
        / "libs"
        / "kotaemon"
        / "kotaemon"
        / "platform_support"
        / "assets"
        / "claude-code"
        / "commands"
    )

    for skill_name in DOCQA_ACTION_SKILLS:
        command_path = commands_dir / f"{skill_name}.md"
        assert command_path.exists()
        command_text = command_path.read_text(encoding="utf-8")
        assert "pip install kotaemon-app" in command_text
        assert "kotaemon app init" in command_text
        assert "kotaemon app doctor" in command_text


def test_claude_kotaemon_action_commands_match_skill_names():
    repo_root = Path(__file__).resolve().parents[3]
    commands_dir = (
        repo_root
        / "libs"
        / "kotaemon"
        / "kotaemon"
        / "platform_support"
        / "assets"
        / "claude-code"
        / "commands"
    )

    for command_name in (
        "kotaemon-cli-operations.md",
        "kotaemon-modelcli.md",
        "kotaemon-app.md",
        "kotaemon-platform.md",
    ):
        assert (commands_dir / command_name).exists()

    for skill_name in MODELCLI_ACTION_SKILLS + APP_ACTION_SKILLS:
        command_path = commands_dir / f"{skill_name}.md"
        assert command_path.exists()
        command_text = command_path.read_text(encoding="utf-8")
        assert "pip install kotaemon-app" in command_text
        assert "kotaemon app init" in command_text
        assert "kotaemon app doctor" in command_text

    for skill_name in PLATFORM_ACTION_SKILLS:
        command_path = commands_dir / f"{skill_name}.md"
        assert command_path.exists()
        command_text = command_path.read_text(encoding="utf-8")
        assert "pip install kotaemon-app" in command_text
        assert "kotaemon platform" in command_text


def test_slide_skill_parity_between_platforms():
    repo_root = Path(__file__).resolve().parents[3]

    for skill_name in (
        "slide",
        "slide-docqa",
        *SLIDE_ACTION_SKILLS,
        *SLIDE_DOCQA_ACTION_SKILLS,
    ):
        codex_skill = (
            repo_root
            / "libs"
            / "kotaemon"
            / "kotaemon"
            / "platform_support"
            / "assets"
            / "codex"
            / "skills"
            / skill_name
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
            / skill_name
            / "SKILL.md"
        ).read_text(encoding="utf-8")

        assert codex_skill == claude_skill


def test_claude_slide_commands_match_skill_names():
    repo_root = Path(__file__).resolve().parents[3]
    commands_dir = (
        repo_root
        / "libs"
        / "kotaemon"
        / "kotaemon"
        / "platform_support"
        / "assets"
        / "claude-code"
        / "commands"
    )

    for command_name in ("slide.md", "slide-docqa.md"):
        command_text = (commands_dir / command_name).read_text(encoding="utf-8")
        assert "pip install slide-cli" in command_text

    for skill_name in SLIDE_ACTION_SKILLS + SLIDE_DOCQA_ACTION_SKILLS:
        command_path = commands_dir / f"{skill_name}.md"
        assert command_path.exists()
        command_text = command_path.read_text(encoding="utf-8")
        assert "pip install slide-cli" in command_text


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
        "pip install kotaemon-app",
        "uv tool install kotaemon-app",
        "kotaemon app init",
        "kotaemon app doctor",
        "kotaemon modelcli init-config --output modelcli.yml",
        "kotaemon modelcli providers --config modelcli.yml",
        'kotaemon modelcli run --prompt "..." --model ds-chat --provider openai --config modelcli.yml --dry-run',
        'kotaemon modelcli run --prompt "..." --model ds-chat --provider openai --config modelcli.yml',
        "kotaemon promptui export <pipeline-path> --output promptui.yml",
        "kotaemon promptui run promptui.yml --port 7860",
        "kotaemon makedoc <module> --output docs.md",
        "kotaemon start-project --template project-default",
        "kotaemon ui",
        "python -m benchmark run --manifest benchmark/manifests/format_robustness.json --suite-name smoke",
    ]

    for token in shared_tokens:
        assert token in codex_skill
        assert token in claude_skill
