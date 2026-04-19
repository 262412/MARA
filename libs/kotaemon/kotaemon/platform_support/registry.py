from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PlatformSpec:
    name: str
    target_subdir: str
    full_components: tuple[str, ...]
    minimal_components: tuple[str, ...]
    selectable_components: tuple[str, ...]

    @property
    def bundle_root(self) -> Path:
        root = files("kotaemon.platform_support.assets").joinpath(self.name)
        return Path(str(root))


_PLATFORM_SPECS: dict[str, PlatformSpec] = {
    "claude-code": PlatformSpec(
        name="claude-code",
        target_subdir=".claude",
        full_components=(
            "commands",
            "skills",
            "agents",
            "rules",
            "hooks",
            "CLAUDE.md",
            "settings.json.template",
        ),
        minimal_components=("skills", "agents", "CLAUDE.md"),
        selectable_components=(
            "commands",
            "skills",
            "agents",
            "rules",
            "hooks",
            "CLAUDE.md",
            "settings.json.template",
        ),
    ),
    "codex": PlatformSpec(
        name="codex",
        target_subdir=".codex",
        full_components=(
            "skills",
            "agents",
            "utils",
            "scripts",
            "AGENTS.md",
            "config.toml.template",
        ),
        minimal_components=("skills", "agents", "AGENTS.md"),
        selectable_components=(
            "skills",
            "agents",
            "utils",
            "scripts",
            "AGENTS.md",
            "config.toml.template",
        ),
    ),
}


def list_platform_names() -> list[str]:
    return list(_PLATFORM_SPECS.keys())


def get_platform_spec(platform_name: str) -> PlatformSpec:
    try:
        return _PLATFORM_SPECS[platform_name]
    except KeyError as exc:
        names = ", ".join(sorted(_PLATFORM_SPECS.keys()))
        raise ValueError(f"Unknown platform '{platform_name}'. Supported: {names}") from exc
