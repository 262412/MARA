from pathlib import Path

from decouple import config

from .theme import Kotaemon as KotaemonTheme

ASSETS_DIR: Path = Path(__file__).parent
ICONS_DIR: Path = ASSETS_DIR / "icons"
PDFJS_VERSION_DIST: str = config("PDFJS_VERSION_DIST", "pdfjs-4.0.379-dist")
PDFJS_PREBUILT_DIR: Path = config(
    "PDFJS_PREBUILT_DIR", Path(__file__).parent / "prebuilt" / PDFJS_VERSION_DIST
)

__all__ = [
    "ASSETS_DIR",
    "ICONS_DIR",
    "KotaemonTheme",
    "PDFJS_VERSION_DIST",
    "PDFJS_PREBUILT_DIR",
]
