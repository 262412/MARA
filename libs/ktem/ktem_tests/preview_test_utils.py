from __future__ import annotations

import threading
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

from pypdf import PdfWriter

OOXML_MARKERS = {
    ".docx": "word/document.xml",
    ".pptx": "ppt/presentation.xml",
    ".xlsx": "xl/workbook.xml",
}


def write_valid_pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with path.open("wb") as file_obj:
        writer.write(file_obj)
    return path


def write_ooxml(path: Path, extension: str | None = None) -> Path:
    marker = OOXML_MARKERS[extension or path.suffix.lower()]
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(marker, "<document />")
        archive.writestr("[Content_Types].xml", "<Types />")
    return path


class SuccessfulSofficeRunner:
    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.commands: list[list[str]] = []
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self._lock = threading.Lock()

    def __call__(self, command, **_kwargs):
        with self._lock:
            self.calls += 1
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.commands.append(list(command))
        try:
            if self.delay:
                time.sleep(self.delay)
            output_dir = Path(command[command.index("--outdir") + 1])
            input_path = Path(command[-1])
            write_valid_pdf(output_dir / f"{input_path.stem}.pdf")
            return SimpleNamespace(returncode=0, stdout="converted", stderr="")
        finally:
            with self._lock:
                self.active -= 1
