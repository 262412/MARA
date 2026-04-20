from __future__ import annotations

from dataclasses import dataclass, field
import json
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


def validate_bundle(platform_name: str | None = None) -> list[ValidationResult]:
    platforms = [platform_name] if platform_name else list_platform_names()
    output: list[ValidationResult] = []

    for current in platforms:
        spec = get_platform_spec(current)
        errors: list[str] = []

        if not spec.bundle_root.exists():
            errors.append(f"Bundle root not found: {spec.bundle_root}")
            output.append(ValidationResult(platform=current, valid=False, errors=errors))
            continue

        for component in spec.selectable_components:
            if not (spec.bundle_root / component).exists():
                errors.append(f"Missing component in bundle: {component}")

        if current == "claude-code":
            for rel in _REQUIRED_HOOK_FILES:
                if not (spec.bundle_root / rel).exists():
                    errors.append(f"Missing required hook asset: {rel.as_posix()}")

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

        output.append(ValidationResult(platform=current, valid=not errors, errors=errors))

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

    return ValidationResult(platform=platform_name, valid=not errors, errors=errors)
