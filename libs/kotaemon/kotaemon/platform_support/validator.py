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

_REQUIRED_SLIDE_SKILL_FILES = (
    Path("skills/slide/SKILL.md"),
    Path("skills/slide-apply/SKILL.md"),
    Path("skills/slide-app/SKILL.md"),
    Path("skills/slide-app-doctor/SKILL.md"),
    Path("skills/slide-app-init/SKILL.md"),
    Path("skills/slide-app-run/SKILL.md"),
    Path("skills/slide-chat/SKILL.md"),
    Path("skills/slide-delete/SKILL.md"),
    Path("skills/slide-doctor/SKILL.md"),
    Path("skills/slide-export-pdf/SKILL.md"),
    Path("skills/slide-extract/SKILL.md"),
    Path("skills/slide-files/SKILL.md"),
    Path("skills/slide-inspect/SKILL.md"),
    Path("skills/slide-model/SKILL.md"),
    Path("skills/slide-model-init-config/SKILL.md"),
    Path("skills/slide-model-providers/SKILL.md"),
    Path("skills/slide-model-run/SKILL.md"),
    Path("skills/slide-platform/SKILL.md"),
    Path("skills/slide-platform-install/SKILL.md"),
    Path("skills/slide-platform-list/SKILL.md"),
    Path("skills/slide-platform-status/SKILL.md"),
    Path("skills/slide-platform-validate/SKILL.md"),
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

_REQUIRED_CLAUDE_SLIDE_COMMAND_FILES = (
    Path("commands/slide.md"),
    Path("commands/slide-apply.md"),
    Path("commands/slide-app.md"),
    Path("commands/slide-app-doctor.md"),
    Path("commands/slide-app-init.md"),
    Path("commands/slide-app-run.md"),
    Path("commands/slide-chat.md"),
    Path("commands/slide-delete.md"),
    Path("commands/slide-doctor.md"),
    Path("commands/slide-export-pdf.md"),
    Path("commands/slide-extract.md"),
    Path("commands/slide-files.md"),
    Path("commands/slide-inspect.md"),
    Path("commands/slide-model.md"),
    Path("commands/slide-model-init-config.md"),
    Path("commands/slide-model-providers.md"),
    Path("commands/slide-model-run.md"),
    Path("commands/slide-platform.md"),
    Path("commands/slide-platform-install.md"),
    Path("commands/slide-platform-list.md"),
    Path("commands/slide-platform-status.md"),
    Path("commands/slide-platform-validate.md"),
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

        for rel in _REQUIRED_SLIDE_SKILL_FILES:
            if not (spec.bundle_root / rel).exists():
                errors.append(f"Missing required slide skill asset: {rel.as_posix()}")
        for rel in _REQUIRED_SLIDE_DOCQA_SKILL_FILES:
            if not (spec.bundle_root / rel).exists():
                errors.append(
                    f"Missing required slide DocQA skill asset: {rel.as_posix()}"
                )
        if current == "claude-code":
            for rel in _REQUIRED_HOOK_FILES:
                if not (spec.bundle_root / rel).exists():
                    errors.append(f"Missing required hook asset: {rel.as_posix()}")

            for rel in _REQUIRED_CLAUDE_SLIDE_COMMAND_FILES:
                if not (spec.bundle_root / rel).exists():
                    errors.append(
                        f"Missing required slide command asset: {rel.as_posix()}"
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
                if "BEGIN SLIDE PLATFORM BLOCK" not in text:
                    errors.append(
                        "config.toml.template must include BEGIN SLIDE PLATFORM BLOCK"
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
        if platform_name == "claude-code":
            commands_dir = resolved_target / "commands"
            if commands_dir.exists():
                for rel in _REQUIRED_CLAUDE_SLIDE_COMMAND_FILES:
                    if not (resolved_target / rel).exists():
                        errors.append(
                            "Missing installed slide command asset: "
                            f"{rel.as_posix()}"
                        )

    return ValidationResult(platform=platform_name, valid=not errors, errors=errors)
