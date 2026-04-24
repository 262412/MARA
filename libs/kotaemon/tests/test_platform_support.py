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

SLIDE_TOP_LEVEL_SKILLS = (
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
)
SLIDE_DOCQA_SKILLS = (
    "slide-docqa",
    "slide-docqa-ask",
    "slide-docqa-chat",
    "slide-docqa-delete",
    "slide-docqa-doctor",
    "slide-docqa-files",
    "slide-docqa-index",
    "slide-docqa-resume",
    "slide-docqa-sessions",
)
SLIDE_APP_SKILLS = (
    "slide-app",
    "slide-app-doctor",
    "slide-app-init",
    "slide-app-run",
)
SLIDE_MODEL_SKILLS = (
    "slide-model",
    "slide-model-init-config",
    "slide-model-providers",
    "slide-model-run",
)
SLIDE_PLATFORM_SKILLS = (
    "slide-platform",
    "slide-platform-install",
    "slide-platform-list",
    "slide-platform-status",
    "slide-platform-validate",
)
CANONICAL_PROJECT_SKILLS = {
    *SLIDE_TOP_LEVEL_SKILLS,
    *SLIDE_DOCQA_SKILLS,
    *SLIDE_APP_SKILLS,
    *SLIDE_MODEL_SKILLS,
    *SLIDE_PLATFORM_SKILLS,
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


def test_platform_registry_names():
    assert set(list_platform_names()) == {"claude-code", "codex"}


def test_install_claude_minimal_creates_slide_only_assets(tmp_path):
    result = install_platform(
        platform_name="claude-code",
        mode="minimal",
        target_dir=tmp_path,
    )

    assert result.platform == "claude-code"
    assert (tmp_path / "skills").exists()
    assert (tmp_path / "agents").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert _skill_names(tmp_path / "skills") == CANONICAL_PROJECT_SKILLS


def test_install_codex_minimal_creates_slide_only_assets(tmp_path):
    result = install_platform(
        platform_name="codex",
        mode="minimal",
        target_dir=tmp_path,
    )

    assert result.platform == "codex"
    assert (tmp_path / "skills").exists()
    assert (tmp_path / "agents").exists()
    assert (tmp_path / "AGENTS.md").exists()
    assert _skill_names(tmp_path / "skills") == CANONICAL_PROJECT_SKILLS


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
    assert (tmp_path / "settings.slide.template.json").exists()
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

    sidecar = tmp_path / "AGENTS.slide.md"
    assert primary.read_text(encoding="utf-8") == "user owned content\n"
    assert sidecar.exists()
    assert str(sidecar) in result.sidecar_paths


def test_install_uses_slide_named_sidecars_and_metadata(tmp_path):
    install_platform(
        platform_name="codex",
        mode="full",
        target_dir=tmp_path / "codex",
    )
    install_platform(
        platform_name="claude-code",
        mode="full",
        target_dir=tmp_path / "claude",
    )

    assert (tmp_path / "codex" / "config.slide.template.toml").exists()
    assert (tmp_path / "codex" / ".slide-platform-install.json").exists()
    assert not (tmp_path / "codex" / "config.kotaemon.template.toml").exists()
    assert not (tmp_path / "codex" / ".kotaemon-platform-install.json").exists()

    assert (tmp_path / "claude" / "settings.slide.template.json").exists()
    assert (tmp_path / "claude" / ".slide-platform-install.json").exists()
    assert not (tmp_path / "claude" / "settings.kotaemon.template.json").exists()
    assert not (tmp_path / "claude" / ".kotaemon-platform-install.json").exists()


def test_install_claude_selective_commands_match_slide_skill_surface(tmp_path):
    result = install_platform(
        platform_name="claude-code",
        mode="selective",
        items=["commands"],
        target_dir=tmp_path,
    )

    assert result.platform == "claude-code"
    assert _claude_command_names(tmp_path / "commands") == CANONICAL_PROJECT_SKILLS


def test_validate_bundle_passes_for_packaged_assets():
    results = validate_bundle()
    assert results
    assert all(item.valid for item in results), [
        (item.platform, item.errors) for item in results
    ]


def test_platform_skill_surfaces_are_exactly_slide_only():
    repo_root = Path(__file__).resolve().parents[3]
    root_codex_skills = repo_root / ".codex" / "skills"
    packaged_codex_skills = _platform_assets_root("codex") / "skills"
    packaged_claude_skills = _platform_assets_root("claude-code") / "skills"
    claude_commands = _platform_assets_root("claude-code") / "commands"

    assert _skill_names(root_codex_skills) == CANONICAL_PROJECT_SKILLS
    assert _skill_names(packaged_codex_skills) == CANONICAL_PROJECT_SKILLS
    assert _skill_names(packaged_claude_skills) == CANONICAL_PROJECT_SKILLS
    assert _claude_command_names(claude_commands) == CANONICAL_PROJECT_SKILLS

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


def test_no_kotaemon_skills_or_commands_are_user_facing():
    repo_root = Path(__file__).resolve().parents[3]
    roots = [
        repo_root / ".codex" / "skills",
        _platform_assets_root("codex") / "skills",
        _platform_assets_root("claude-code") / "skills",
    ]

    for root in roots:
        assert not any(name.startswith("kotaemon-") for name in _skill_names(root))
    assert not any(
        name.startswith("kotaemon-")
        for name in _claude_command_names(
            _platform_assets_root("claude-code") / "commands"
        )
    )


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
