"""Minimal Gradio file-serving roots for preview and static UI assets."""

from __future__ import annotations

from pathlib import Path

from ktem.assets import ICONS_DIR


def build_gradio_allowed_paths(
    *,
    pdfjs_dir: Path | str,
    gradio_temp_dir: Path | str,
    doc_dir: Path | str,
) -> list[str]:
    """Return only roots intentionally visible through Gradio's file route."""
    preview_dir = Path(gradio_temp_dir).expanduser().resolve() / "pdf_previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    return [
        str(ICONS_DIR.resolve()),
        str(Path(pdfjs_dir).expanduser().resolve()),
        str(Path(doc_dir).expanduser().resolve()),
        str(preview_dir),
    ]


__all__ = ["build_gradio_allowed_paths"]
