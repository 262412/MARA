from __future__ import annotations

import json
import re
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

_REQUIRED_MARA_SKILL_FILES = (
    Path("skills/MARA/SKILL.md"),
    Path("skills/MARA-apply/SKILL.md"),
    Path("skills/MARA-app/SKILL.md"),
    Path("skills/MARA-app-doctor/SKILL.md"),
    Path("skills/MARA-app-init/SKILL.md"),
    Path("skills/MARA-app-run/SKILL.md"),
    Path("skills/MARA-chat/SKILL.md"),
    Path("skills/MARA-delete/SKILL.md"),
    Path("skills/MARA-doctor/SKILL.md"),
    Path("skills/MARA-export-pdf/SKILL.md"),
    Path("skills/MARA-extract/SKILL.md"),
    Path("skills/MARA-files/SKILL.md"),
    Path("skills/MARA-inspect/SKILL.md"),
    Path("skills/MARA-model/SKILL.md"),
    Path("skills/MARA-model-init-config/SKILL.md"),
    Path("skills/MARA-model-providers/SKILL.md"),
    Path("skills/MARA-model-run/SKILL.md"),
    Path("skills/MARA-platform/SKILL.md"),
    Path("skills/MARA-platform-install/SKILL.md"),
    Path("skills/MARA-platform-list/SKILL.md"),
    Path("skills/MARA-platform-status/SKILL.md"),
    Path("skills/MARA-platform-validate/SKILL.md"),
    Path("skills/MARA-read/SKILL.md"),
    Path("skills/MARA-read-slide/SKILL.md"),
    Path("skills/MARA-resume/SKILL.md"),
    Path("skills/MARA-review/SKILL.md"),
    Path("skills/MARA-run/SKILL.md"),
    Path("skills/MARA-search/SKILL.md"),
    Path("skills/MARA-sessions/SKILL.md"),
    Path("skills/MARA-shell/SKILL.md"),
    Path("skills/MARA-write/SKILL.md"),
)

_REQUIRED_MARA_DOCQA_SKILL_FILES = (
    Path("skills/MARA-docqa/SKILL.md"),
    Path("skills/MARA-docqa-artifacts/SKILL.md"),
    Path("skills/MARA-docqa-ask/SKILL.md"),
    Path("skills/MARA-docqa-chat/SKILL.md"),
    Path("skills/MARA-docqa-delete/SKILL.md"),
    Path("skills/MARA-docqa-doctor/SKILL.md"),
    Path("skills/MARA-docqa-files/SKILL.md"),
    Path("skills/MARA-docqa-index/SKILL.md"),
    Path("skills/MARA-docqa-notes/SKILL.md"),
    Path("skills/MARA-docqa-resume/SKILL.md"),
    Path("skills/MARA-docqa-sessions/SKILL.md"),
    Path("skills/MARA-docqa-sources/SKILL.md"),
)

_REQUIRED_CLAUDE_MARA_COMMAND_FILES = (
    Path("commands/MARA.md"),
    Path("commands/MARA-apply.md"),
    Path("commands/MARA-app.md"),
    Path("commands/MARA-app-doctor.md"),
    Path("commands/MARA-app-init.md"),
    Path("commands/MARA-app-run.md"),
    Path("commands/MARA-chat.md"),
    Path("commands/MARA-delete.md"),
    Path("commands/MARA-doctor.md"),
    Path("commands/MARA-export-pdf.md"),
    Path("commands/MARA-extract.md"),
    Path("commands/MARA-files.md"),
    Path("commands/MARA-inspect.md"),
    Path("commands/MARA-model.md"),
    Path("commands/MARA-model-init-config.md"),
    Path("commands/MARA-model-providers.md"),
    Path("commands/MARA-model-run.md"),
    Path("commands/MARA-platform.md"),
    Path("commands/MARA-platform-install.md"),
    Path("commands/MARA-platform-list.md"),
    Path("commands/MARA-platform-status.md"),
    Path("commands/MARA-platform-validate.md"),
    Path("commands/MARA-read.md"),
    Path("commands/MARA-read-slide.md"),
    Path("commands/MARA-resume.md"),
    Path("commands/MARA-review.md"),
    Path("commands/MARA-run.md"),
    Path("commands/MARA-search.md"),
    Path("commands/MARA-sessions.md"),
    Path("commands/MARA-shell.md"),
    Path("commands/MARA-write.md"),
    Path("commands/MARA-docqa.md"),
    Path("commands/MARA-docqa-artifacts.md"),
    Path("commands/MARA-docqa-ask.md"),
    Path("commands/MARA-docqa-chat.md"),
    Path("commands/MARA-docqa-delete.md"),
    Path("commands/MARA-docqa-doctor.md"),
    Path("commands/MARA-docqa-files.md"),
    Path("commands/MARA-docqa-index.md"),
    Path("commands/MARA-docqa-notes.md"),
    Path("commands/MARA-docqa-resume.md"),
    Path("commands/MARA-docqa-sessions.md"),
    Path("commands/MARA-docqa-sources.md"),
)

_SKILL_DIR_SUPPORT_REF_RE = re.compile(
    r"(?:\$SKILL_DIR|\$\{SKILL_DIR\})[\\/]"
    r"(?P<path>(?:scripts|references|assets)[\\/][A-Za-z0-9_.\\/:-]+)"
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

        for rel in _REQUIRED_MARA_SKILL_FILES:
            if not (spec.bundle_root / rel).exists():
                errors.append(f"Missing required MARA skill asset: {rel.as_posix()}")
        for rel in _REQUIRED_MARA_DOCQA_SKILL_FILES:
            if not (spec.bundle_root / rel).exists():
                errors.append(
                    f"Missing required MARA DocQA skill asset: {rel.as_posix()}"
                )
        errors.extend(
            _missing_skill_support_file_errors(
                spec.bundle_root,
                prefix="Missing skill support file referenced by",
            )
        )
        if current == "claude-code":
            for rel in _REQUIRED_HOOK_FILES:
                if not (spec.bundle_root / rel).exists():
                    errors.append(f"Missing required hook asset: {rel.as_posix()}")

            for rel in _REQUIRED_CLAUDE_MARA_COMMAND_FILES:
                if not (spec.bundle_root / rel).exists():
                    errors.append(
                        f"Missing required MARA command asset: {rel.as_posix()}"
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
                if "BEGIN MARA PLATFORM BLOCK" not in text:
                    errors.append(
                        "config.toml.template must include BEGIN MARA PLATFORM BLOCK"
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
            for rel in _REQUIRED_MARA_SKILL_FILES:
                if not (resolved_target / rel).exists():
                    errors.append(
                        "Missing installed MARA skill asset: " f"{rel.as_posix()}"
                    )
            for rel in _REQUIRED_MARA_DOCQA_SKILL_FILES:
                if not (resolved_target / rel).exists():
                    errors.append(
                        "Missing installed MARA DocQA skill asset: " f"{rel.as_posix()}"
                    )
        if platform_name == "claude-code":
            commands_dir = resolved_target / "commands"
            if commands_dir.exists():
                for rel in _REQUIRED_CLAUDE_MARA_COMMAND_FILES:
                    if not (resolved_target / rel).exists():
                        errors.append(
                            "Missing installed MARA command asset: " f"{rel.as_posix()}"
                        )
        errors.extend(
            _missing_skill_support_file_errors(
                resolved_target,
                prefix="Missing installed skill support file referenced by",
            )
        )

    return ValidationResult(platform=platform_name, valid=not errors, errors=errors)


def _missing_skill_support_file_errors(root: Path, prefix: str) -> list[str]:
    skills_dir = root / "skills"
    if not skills_dir.exists():
        return []

    errors: list[str] = []
    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        text = skill_file.read_text(encoding="utf-8")
        skill_rel = skill_file.relative_to(root).as_posix()
        for ref_rel in _iter_skill_dir_support_refs(root, skill_file, text):
            if not (root / ref_rel).exists():
                errors.append(f"{prefix} {skill_rel}: {ref_rel.as_posix()}")
    return errors


def _iter_skill_dir_support_refs(
    root: Path,
    skill_file: Path,
    text: str,
) -> list[Path]:
    refs: list[Path] = []
    for match in _SKILL_DIR_SUPPORT_REF_RE.finditer(text):
        support_path = match.group("path").replace("\\", "/")
        candidate = skill_file.parent / Path(support_path)
        try:
            refs.append(candidate.relative_to(root))
        except ValueError:
            continue
    return refs
