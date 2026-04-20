from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .registry import PlatformSpec, get_platform_spec


@dataclass(slots=True)
class InstallResult:
    platform: str
    mode: str
    target_dir: Path
    components: list[str] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)
    merged_paths: list[str] = field(default_factory=list)
    sidecar_paths: list[str] = field(default_factory=list)
    backup_dir: Path | None = None
    dry_run: bool = False


@dataclass(slots=True)
class PlatformStatus:
    platform: str
    target_dir: Path
    component_state: dict[str, bool]


def resolve_target_dir(
    spec: PlatformSpec, target_dir: str | Path | None = None
) -> Path:
    if target_dir is not None:
        return Path(target_dir).expanduser().resolve()
    return (Path.home() / spec.target_subdir).resolve()


def select_components(
    spec: PlatformSpec,
    mode: str,
    items: Sequence[str] | None = None,
) -> list[str]:
    if mode == "full":
        return list(spec.full_components)
    if mode == "minimal":
        return list(spec.minimal_components)
    if mode != "selective":
        raise ValueError(f"Unsupported mode '{mode}'.")

    selected = [item for item in (items or []) if item]
    if not selected:
        raise ValueError("Selective mode requires at least one --item value.")

    invalid = sorted(set(selected) - set(spec.selectable_components))
    if invalid:
        valid = ", ".join(spec.selectable_components)
        raise ValueError(
            "Invalid selective items: " f"{', '.join(invalid)}. Valid values: {valid}"
        )
    return list(dict.fromkeys(selected))


def install_platform(
    platform_name: str,
    mode: str,
    target_dir: str | Path | None = None,
    items: Sequence[str] | None = None,
    dry_run: bool = False,
) -> InstallResult:
    spec = get_platform_spec(platform_name)
    selected = select_components(spec, mode=mode, items=items)
    resolved_target = resolve_target_dir(spec, target_dir=target_dir)

    result = InstallResult(
        platform=platform_name,
        mode=mode,
        target_dir=resolved_target,
        components=selected,
        dry_run=dry_run,
    )

    if not dry_run:
        resolved_target.mkdir(parents=True, exist_ok=True)

    for component in selected:
        source = spec.bundle_root / component
        if not source.exists():
            raise FileNotFoundError(
                f"Component '{component}' is missing from bundle {spec.bundle_root}"
            )

        if component in ("CLAUDE.md", "AGENTS.md"):
            _install_primary_doc(spec, source, result)
            continue

        if component == "settings.json.template":
            _apply_claude_settings_template(spec, source, result)
            continue

        if component == "config.toml.template":
            _apply_codex_config_template(spec, source, result)
            continue

        destination = resolved_target / component
        _sync_path(spec, source, destination, result)

    _write_install_metadata(result)
    return result


def platform_status(
    platform_name: str,
    target_dir: str | Path | None = None,
) -> PlatformStatus:
    spec = get_platform_spec(platform_name)
    resolved_target = resolve_target_dir(spec, target_dir=target_dir)

    state = {
        component: _component_present(spec, resolved_target, component)
        for component in spec.selectable_components
    }
    return PlatformStatus(
        platform=platform_name,
        target_dir=resolved_target,
        component_state=state,
    )


def _component_present(spec: PlatformSpec, target_dir: Path, component: str) -> bool:
    if component == "CLAUDE.md":
        return (target_dir / "CLAUDE.md").exists() or (
            target_dir / "CLAUDE.kotaemon.md"
        ).exists()
    if component == "AGENTS.md":
        return (target_dir / "AGENTS.md").exists() or (
            target_dir / "AGENTS.kotaemon.md"
        ).exists()
    if component == "settings.json.template":
        return (target_dir / "settings.kotaemon.template.json").exists() or (
            target_dir / "settings.json"
        ).exists()
    if component == "config.toml.template":
        return (target_dir / "config.kotaemon.template.toml").exists() or (
            target_dir / "config.toml"
        ).exists()

    return (target_dir / component).exists()


def _sync_path(
    spec: PlatformSpec,
    source: Path,
    destination: Path,
    result: InstallResult,
) -> None:
    if destination.exists():
        _backup_existing(spec, destination, result)

    if result.dry_run:
        result.changed_paths.append(str(destination))
        return

    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    result.changed_paths.append(str(destination))


def _install_primary_doc(
    spec: PlatformSpec,
    source: Path,
    result: InstallResult,
) -> None:
    target = result.target_dir / source.name
    sidecar = result.target_dir / f"{source.stem}.kotaemon{source.suffix}"
    destination = target if not target.exists() else sidecar

    if destination.exists():
        _backup_existing(spec, destination, result)

    if result.dry_run:
        result.changed_paths.append(str(destination))
        if destination == sidecar:
            result.sidecar_paths.append(str(sidecar))
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    result.changed_paths.append(str(destination))

    if destination == sidecar:
        result.sidecar_paths.append(str(sidecar))


def _apply_claude_settings_template(
    spec: PlatformSpec,
    source: Path,
    result: InstallResult,
) -> None:
    sidecar = result.target_dir / "settings.kotaemon.template.json"
    if sidecar.exists():
        _backup_existing(spec, sidecar, result)

    template_data = json.loads(source.read_text(encoding="utf-8"))
    settings_path = result.target_dir / "settings.json"
    existing_data: dict[str, Any] = {}

    if settings_path.exists():
        existing_data = json.loads(settings_path.read_text(encoding="utf-8"))
        _backup_existing(spec, settings_path, result)

    merged_data, changed = _merge_missing(existing_data, template_data)

    if result.dry_run:
        result.changed_paths.append(str(sidecar))
        if changed or not settings_path.exists():
            result.merged_paths.append(str(settings_path))
        return

    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    result.changed_paths.append(str(sidecar))

    if changed or not settings_path.exists():
        settings_path.write_text(
            json.dumps(merged_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        result.merged_paths.append(str(settings_path))


def _apply_codex_config_template(
    spec: PlatformSpec,
    source: Path,
    result: InstallResult,
) -> None:
    sidecar = result.target_dir / "config.kotaemon.template.toml"
    if sidecar.exists():
        _backup_existing(spec, sidecar, result)

    template_text = source.read_text(encoding="utf-8")
    config_path = result.target_dir / "config.toml"

    if config_path.exists():
        existing_text = config_path.read_text(encoding="utf-8")
        _backup_existing(spec, config_path, result)
    else:
        existing_text = ""

    marker = "BEGIN KOTAEMON PLATFORM BLOCK"
    if marker in existing_text:
        merged_text = existing_text
        changed = False
    elif existing_text.strip():
        merged_text = existing_text.rstrip() + "\n\n" + template_text.strip() + "\n"
        changed = True
    else:
        merged_text = template_text.strip() + "\n"
        changed = True

    if result.dry_run:
        result.changed_paths.append(str(sidecar))
        if changed:
            result.merged_paths.append(str(config_path))
        return

    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(template_text, encoding="utf-8")
    result.changed_paths.append(str(sidecar))

    if changed:
        config_path.write_text(merged_text, encoding="utf-8")
        result.merged_paths.append(str(config_path))


def _merge_missing(base: Any, incoming: Any) -> tuple[Any, bool]:
    if isinstance(base, dict) and isinstance(incoming, dict):
        merged: dict[str, Any] = dict(base)
        changed = False
        for key, value in incoming.items():
            if key not in merged:
                merged[key] = value
                changed = True
                continue
            nested, nested_changed = _merge_missing(merged[key], value)
            if nested_changed:
                merged[key] = nested
                changed = True
        return merged, changed

    if isinstance(base, list) and isinstance(incoming, list):
        merged_list = list(base)
        changed = False
        seen = {_stable_key(item) for item in merged_list}
        for item in incoming:
            key = _stable_key(item)
            if key in seen:
                continue
            seen.add(key)
            merged_list.append(item)
            changed = True
        return merged_list, changed

    return base, False


def _stable_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _backup_existing(
    spec: PlatformSpec,
    destination: Path,
    result: InstallResult,
) -> None:
    if not destination.exists():
        return

    backup_dir = _ensure_backup_dir(spec, result)
    if backup_dir is None:
        return

    rel = destination.relative_to(result.target_dir)
    backup_path = backup_dir / rel

    if result.dry_run:
        return

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_dir():
        shutil.copytree(destination, backup_path, dirs_exist_ok=True)
    else:
        shutil.copy2(destination, backup_path)


def _ensure_backup_dir(spec: PlatformSpec, result: InstallResult) -> Path | None:
    if result.backup_dir is not None:
        return result.backup_dir

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = result.target_dir / ".kotaemon-platform-backups" / stamp
    result.backup_dir = backup_dir

    if result.dry_run:
        return backup_dir

    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def _write_install_metadata(result: InstallResult) -> None:
    metadata_path = result.target_dir / ".kotaemon-platform-install.json"
    payload = {
        "platform": result.platform,
        "mode": result.mode,
        "components": result.components,
        "changed_paths": result.changed_paths,
        "merged_paths": result.merged_paths,
        "sidecar_paths": result.sidecar_paths,
        "backup_dir": str(result.backup_dir) if result.backup_dir else None,
        "dry_run": result.dry_run,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    if result.dry_run:
        return

    metadata_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
