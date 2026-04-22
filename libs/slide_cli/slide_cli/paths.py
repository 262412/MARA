from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import PlatformDirs

DEFAULT_APP_NAME = "slide-cli"
DEFAULT_APP_AUTHOR = "Cinnamon"


@dataclass(frozen=True)
class SlideSessionPaths:
    session_id: str
    session_dir: Path
    metadata_path: Path
    transcript_dir: Path
    transcript_path: Path
    artifacts_dir: Path
    patches_dir: Path

    def ensure_exists(self) -> "SlideSessionPaths":
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.patches_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.transcript_path.exists():
            self.transcript_path.touch()
        return self


@dataclass(frozen=True)
class SlideRuntimePaths:
    config_dir: Path
    data_dir: Path
    cache_dir: Path
    sessions_dir: Path
    default_config_path: Path

    def ensure_exists(self) -> "SlideRuntimePaths":
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        return self

    def session_paths(self, session_id: str) -> SlideSessionPaths:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            raise ValueError("session_id must be provided.")

        session_dir = self.sessions_dir / normalized_session_id
        transcript_dir = session_dir / "transcript"
        return SlideSessionPaths(
            session_id=normalized_session_id,
            session_dir=session_dir,
            metadata_path=session_dir / "session.json",
            transcript_dir=transcript_dir,
            transcript_path=transcript_dir / "events.jsonl",
            artifacts_dir=session_dir / "artifacts",
            patches_dir=session_dir / "patches",
        )


def get_slide_runtime_paths(
    *,
    base_dir: str | Path | None = None,
    app_name: str = DEFAULT_APP_NAME,
    app_author: str = DEFAULT_APP_AUTHOR,
) -> SlideRuntimePaths:
    if base_dir is not None:
        root_dir = Path(base_dir).expanduser().resolve()
        config_dir = root_dir / "config"
        data_dir = root_dir / "data"
        cache_dir = root_dir / "cache"
        sessions_dir = root_dir / "sessions"
    else:
        dirs = PlatformDirs(appname=app_name, appauthor=app_author)
        config_dir = Path(dirs.user_config_dir).resolve()
        data_dir = Path(dirs.user_data_dir).resolve()
        cache_dir = Path(dirs.user_cache_dir).resolve()
        sessions_dir = data_dir / "sessions"

    return SlideRuntimePaths(
        config_dir=config_dir,
        data_dir=data_dir,
        cache_dir=cache_dir,
        sessions_dir=sessions_dir,
        default_config_path=config_dir / "modelcli.yml",
    )


__all__ = [
    "DEFAULT_APP_AUTHOR",
    "DEFAULT_APP_NAME",
    "SlideRuntimePaths",
    "SlideSessionPaths",
    "get_slide_runtime_paths",
]
