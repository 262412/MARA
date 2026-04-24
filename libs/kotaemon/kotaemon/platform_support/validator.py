from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .installer import platform_status, resolve_target_dir
from .registry import get_platform_spec, list_platform_names


@dataclass(slots=True)
class ValidationResult:
    platform: str
    valid: bool
    errors: list[str] = field(default_factory=list)


_REQUIRED_HOOK_FILES = (
    Path("hooks/hooks.json"),
    Path("hooks/scripts/security-guard.sh"),
)

_REQUIRED_DOCQA_SKILL_FILES = (
    Path("skills/kotaemon-docqa/SKILL.md"),
    Path("skills/kotaemon-docqa-ask/SKILL.md"),
    Path("skills/kotaemon-docqa-index/SKILL.md"),
    Path("skills/kotaemon-docqa-chat/SKILL.md"),
    Path("skills/kotaemon-docqa-files/SKILL.md"),
    Path("skills/kotaemon-docqa-delete/SKILL.md"),
    Path("skills/kotaemon-docqa-sessions/SKILL.md"),
    Path("skills/kotaemon-docqa-resume/SKILL.md"),
    Path("skills/kotaemon-docqa-doctor/SKILL.md"),
    Path("skills/kotaemon-docqa-acceptance/SKILL.md"),
)

_REQUIRED_SLIDE_SKILL_FILES = (
    Path("skills/slide/SKILL.md"),
    Path("skills/slide-apply/SKILL.md"),
    Path("skills/slide-chat/SKILL.md"),
    Path("skills/slide-delete/SKILL.md"),
    Path("skills/slide-doctor/SKILL.md"),
    Path("skills/slide-export-pdf/SKILL.md"),
    Path("skills/slide-extract/SKILL.md"),
    Path("skills/slide-files/SKILL.md"),
    Path("skills/slide-inspect/SKILL.md"),
    Path("skills/slide-read/SKILL.md"),
    Path("skills/slide-read-slide/SKILL.md"),
    Path("skills/slide-resume/SKILL.md"),
    Path("skills/slide-review/SKILL.md"),
    Path("skills/slide-run/SKILL.md"),
    Path("skills/slide-search/SKILL.md"),
    Path("skills/slide-sessions/SKILL.md"),
    Path("skills/slide-shell/SKILL.md"),
    Path("skills/slide-write/SKILL.md"),
)

_REQUIRED_SLIDE_DOCQA_SKILL_FILES = (
    Path("skills/slide-docqa/SKILL.md"),
    Path("skills/slide-docqa-ask/SKILL.md"),
    Path("skills/slide-docqa-chat/SKILL.md"),
    Path("skills/slide-docqa-delete/SKILL.md"),
    Path("skills/slide-docqa-doctor/SKILL.md"),
    Path("skills/slide-docqa-files/SKILL.md"),
    Path("skills/slide-docqa-index/SKILL.md"),
    Path("skills/slide-docqa-resume/SKILL.md"),
    Path("skills/slide-docqa-sessions/SKILL.md"),
)

_REQUIRED_CLAUDE_DOCQA_COMMAND_FILES = (
    Path("commands/kotaemon-docqa.md"),
    Path("commands/kotaemon-docqa-ask.md"),
    Path("commands/kotaemon-docqa-index.md"),
    Path("commands/kotaemon-docqa-chat.md"),
    Path("commands/kotaemon-docqa-files.md"),
    Path("commands/kotaemon-docqa-delete.md"),
    Path("commands/kotaemon-docqa-sessions.md"),
    Path("commands/kotaemon-docqa-resume.md"),
    Path("commands/kotaemon-docqa-doctor.md"),
    Path("commands/kotaemon-docqa-acceptance.md"),
)
_REQUIRED_CLAUDE_SLIDE_COMMAND_FILES = (
    Path("commands/slide.md"),
    Path("commands/slide-apply.md"),
    Path("commands/slide-chat.md"),
    Path("commands/slide-delete.md"),
    Path("commands/slide-doctor.md"),
    Path("commands/slide-export-pdf.md"),
    Path("commands/slide-extract.md"),
    Path("commands/slide-files.md"),
    Path("commands/slide-inspect.md"),
    Path("commands/slide-read.md"),
    Path("commands/slide-read-slide.md"),
    Path("commands/slide-resume.md"),
    Path("commands/slide-review.md"),
    Path("commands/slide-run.md"),
    Path("commands/slide-search.md"),
    Path("commands/slide-sessions.md"),
    Path("commands/slide-shell.md"),
    Path("commands/slide-write.md"),
    Path("commands/slide-docqa.md"),
    Path("commands/slide-docqa-ask.md"),
    Path("commands/slide-docqa-chat.md"),
    Path("commands/slide-docqa-delete.md"),
    Path("commands/slide-docqa-doctor.md"),
    Path("commands/slide-docqa-files.md"),
    Path("commands/slide-docqa-index.md"),
    Path("commands/slide-docqa-resume.md"),
    Path("commands/slide-docqa-sessions.md"),
)
_REQUIRED_MODELCLI_SKILL_FILES = (
    Path("skills/kotaemon-modelcli/SKILL.md"),
    Path("skills/kotaemon-modelcli-init-config/SKILL.md"),
    Path("skills/kotaemon-modelcli-providers/SKILL.md"),
    Path("skills/kotaemon-modelcli-run/SKILL.md"),
)
_REQUIRED_APP_SKILL_FILES = (
    Path("skills/kotaemon-app/SKILL.md"),
    Path("skills/kotaemon-app-init/SKILL.md"),
    Path("skills/kotaemon-app-doctor/SKILL.md"),
    Path("skills/kotaemon-app-run/SKILL.md"),
)
_REQUIRED_CLAUDE_MODELCLI_COMMAND_FILES = (
    Path("commands/kotaemon-modelcli.md"),
    Path("commands/kotaemon-modelcli-init-config.md"),
    Path("commands/kotaemon-modelcli-providers.md"),
    Path("commands/kotaemon-modelcli-run.md"),
)
_REQUIRED_CLAUDE_APP_COMMAND_FILES = (
    Path("commands/kotaemon-app.md"),
    Path("commands/kotaemon-app-init.md"),
    Path("commands/kotaemon-app-doctor.md"),
    Path("commands/kotaemon-app-run.md"),
)


def validate_bundle(platform_name: str | None = None) -> list[ValidationResult]:
    platforms = [platform_name] if platform_name else list_platform_names()
    output: list[ValidationResult] = []

    for current in platforms:
        spec = get_platform_spec(current)
        errors: list[str] = []

        if not spec.bundle_root.exists():
            errors.append(f"Bundle root not found: {spec.bundle_root}")
            output.append(
                ValidationResult(platform=current, valid=False, errors=errors)
            )
            continue

        for component in spec.selectable_components:
            if not (spec.bundle_root / component).exists():
                errors.append(f"Missing component in bundle: {component}")

        for rel in _REQUIRED_DOCQA_SKILL_FILES:
            if not (spec.bundle_root / rel).exists():
                errors.append(f"Missing required DocQA skill asset: {rel.as_posix()}")
        for rel in _REQUIRED_SLIDE_SKILL_FILES:
            if not (spec.bundle_root / rel).exists():
                errors.append(f"Missing required slide skill asset: {rel.as_posix()}")
        for rel in _REQUIRED_SLIDE_DOCQA_SKILL_FILES:
            if not (spec.bundle_root / rel).exists():
                errors.append(
                    f"Missing required slide DocQA skill asset: {rel.as_posix()}"
                )
        for rel in _REQUIRED_MODELCLI_SKILL_FILES:
            if not (spec.bundle_root / rel).exists():
                errors.append(
                    f"Missing required modelcli skill asset: {rel.as_posix()}"
                )
        for rel in _REQUIRED_APP_SKILL_FILES:
            if not (spec.bundle_root / rel).exists():
                errors.append(f"Missing required app skill asset: {rel.as_posix()}")

        if current == "claude-code":
            for rel in _REQUIRED_HOOK_FILES:
                if not (spec.bundle_root / rel).exists():
                    errors.append(f"Missing required hook asset: {rel.as_posix()}")

            for rel in _REQUIRED_CLAUDE_DOCQA_COMMAND_FILES:
                if not (spec.bundle_root / rel).exists():
                    errors.append(
                        f"Missing required DocQA command asset: {rel.as_posix()}"
                    )
            for rel in _REQUIRED_CLAUDE_SLIDE_COMMAND_FILES:
                if not (spec.bundle_root / rel).exists():
                    errors.append(
                        f"Missing required slide command asset: {rel.as_posix()}"
                    )
            for rel in _REQUIRED_CLAUDE_MODELCLI_COMMAND_FILES:
                if not (spec.bundle_root / rel).exists():
                    errors.append(
                        f"Missing required modelcli command asset: {rel.as_posix()}"
                    )
            for rel in _REQUIRED_CLAUDE_APP_COMMAND_FILES:
                if not (spec.bundle_root / rel).exists():
                    errors.append(
                        f"Missing required app command asset: {rel.as_posix()}"
                    )

            hooks_json = spec.bundle_root / "hooks" / "hooks.json"
            if hooks_json.exists():
                try:
                    json.loads(hooks_json.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    errors.append(f"Invalid hooks.json: {exc}")

        if current == "codex":
            config_template = spec.bundle_root / "config.toml.template"
            if config_template.exists():
                text = config_template.read_text(encoding="utf-8")
                if "BEGIN KOTAEMON PLATFORM BLOCK" not in text:
                    errors.append(
                        "config.toml.template must include BEGIN KOTAEMON PLATFORM BLOCK"
                    )

        output.append(
            ValidationResult(platform=current, valid=not errors, errors=errors)
        )

    return output


def validate_installed(
    platform_name: str,
    target_dir: str | Path | None = None,
) -> ValidationResult:
    spec = get_platform_spec(platform_name)
    status = platform_status(platform_name, target_dir=target_dir)
    errors: list[str] = []

    for component in spec.minimal_components:
        if not status.component_state.get(component, False):
            errors.append(f"Missing minimal component in target: {component}")

    resolved_target = resolve_target_dir(spec, target_dir=target_dir)
    if not resolved_target.exists():
        errors.append(f"Target directory not found: {resolved_target}")
    else:
        skills_dir = resolved_target / "skills"
        if skills_dir.exists():
            for rel in _REQUIRED_DOCQA_SKILL_FILES:
                if not (resolved_target / rel).exists():
                    errors.append(
                        "Missing installed DocQA skill asset: " f"{rel.as_posix()}"
                    )
            for rel in _REQUIRED_SLIDE_SKILL_FILES:
                if not (resolved_target / rel).exists():
                    errors.append(
                        "Missing installed slide skill asset: " f"{rel.as_posix()}"
                    )
            for rel in _REQUIRED_SLIDE_DOCQA_SKILL_FILES:
                if not (resolved_target / rel).exists():
                    errors.append(
                        "Missing installed slide DocQA skill asset: "
                        f"{rel.as_posix()}"
                    )
            for rel in _REQUIRED_MODELCLI_SKILL_FILES:
                if not (resolved_target / rel).exists():
                    errors.append(
                        "Missing installed modelcli skill asset: " f"{rel.as_posix()}"
                    )
            for rel in _REQUIRED_APP_SKILL_FILES:
                if not (resolved_target / rel).exists():
                    errors.append(
                        "Missing installed app skill asset: " f"{rel.as_posix()}"
                    )

        if platform_name == "claude-code":
            commands_dir = resolved_target / "commands"
            if commands_dir.exists():
                for rel in _REQUIRED_CLAUDE_DOCQA_COMMAND_FILES:
                    if not (resolved_target / rel).exists():
                        errors.append(
                            "Missing installed DocQA command asset: "
                            f"{rel.as_posix()}"
                        )
                for rel in _REQUIRED_CLAUDE_SLIDE_COMMAND_FILES:
                    if not (resolved_target / rel).exists():
                        errors.append(
                            "Missing installed slide command asset: "
                            f"{rel.as_posix()}"
                        )
                for rel in _REQUIRED_CLAUDE_MODELCLI_COMMAND_FILES:
                    if not (resolved_target / rel).exists():
                        errors.append(
                            "Missing installed modelcli command asset: "
                            f"{rel.as_posix()}"
                        )
                for rel in _REQUIRED_CLAUDE_APP_COMMAND_FILES:
                    if not (resolved_target / rel).exists():
                        errors.append(
                            "Missing installed app command asset: " f"{rel.as_posix()}"
                        )

    return ValidationResult(platform=platform_name, valid=not errors, errors=errors)
