"""External deck conversion and ownership of each export workspace."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

PathLike = str | Path


def export_deck_pdf(
    source_path: PathLike,
    *,
    output_path: PathLike | None = None,
    soffice_path: str | None = None,
    timeout_sec: int = 120,
) -> Path:
    source = Path(source_path).resolve()
    if not source.exists():
        raise FileNotFoundError(source)

    resolved_soffice = (
        soffice_path or os.environ.get("SOFFICE_PATH") or shutil.which("soffice")
    )
    if not resolved_soffice:
        raise RuntimeError("LibreOffice is required to export slide decks to PDF.")

    requested_output = Path(output_path).resolve() if output_path is not None else None
    target_dir = (
        requested_output.parent if requested_output is not None else source.parent
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    with _export_workspace(target_dir) as workspace:
        completed = subprocess.run(
            [
                str(resolved_soffice),
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(workspace),
                str(source),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_sec,
            check=False,
        )
        if completed.returncode != 0:
            details = (
                completed.stderr.strip() or completed.stdout.strip() or "unknown error"
            )
            raise RuntimeError(f"LibreOffice export failed: {details}")

        converted_path = workspace / f"{source.stem}.pdf"
        if not converted_path.is_file():
            raise RuntimeError(
                "LibreOffice export did not create the expected PDF output."
            )

        destination = requested_output or target_dir / f"{source.stem}.pdf"
        converted_path.replace(destination)
        return destination


@contextmanager
def _export_workspace(target_dir: Path):
    """Clean only this conversion's directory without masking a primary error."""
    workspace = Path(tempfile.mkdtemp(prefix=".mara-deck-", dir=target_dir))
    failed = False
    try:
        yield workspace
    except BaseException:
        failed = True
        raise
    finally:
        try:
            shutil.rmtree(workspace)
        except OSError:
            if not failed:
                raise
            logging.getLogger(__name__).exception(
                "Failed to remove owned deck conversion directory %s", workspace
            )
