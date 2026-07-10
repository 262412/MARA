from pathlib import Path

from .pdfjs_assets import PDFJS_VERSION, PDFJS_VERSION_DIST, get_pdfjs_runtime_dir
from .theme import Kotaemon as KotaemonTheme

ASSETS_DIR: Path = Path(__file__).parent
ICONS_DIR: Path = ASSETS_DIR / "icons"
PDFJS_PREBUILT_DIR: Path = get_pdfjs_runtime_dir()

__all__ = [
    "ASSETS_DIR",
    "ICONS_DIR",
    "KotaemonTheme",
    "PDFJS_VERSION",
    "PDFJS_VERSION_DIST",
    "PDFJS_PREBUILT_DIR",
    "get_pdfjs_runtime_dir",
]
