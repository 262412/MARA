from __future__ import annotations

import threading
import time
import zipfile
from pathlib import Path
from struct import pack_into
from types import SimpleNamespace

from pypdf import PdfWriter

OOXML_MARKERS = {
    ".docx": "word/document.xml",
    ".pptx": "ppt/presentation.xml",
    ".xlsx": "xl/workbook.xml",
}
CFB_STREAM_NAMES = {
    ".doc": "WordDocument",
    ".ppt": "PowerPoint Document",
    ".xls": "Workbook",
}
_CFB_FREE_SECTOR = 0xFFFFFFFF
_CFB_END_OF_CHAIN = 0xFFFFFFFE
_CFB_FAT_SECTOR = 0xFFFFFFFD


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


def _write_cfb_directory_entry(
    directory: bytearray,
    index: int,
    name: str,
    object_type: int,
    *,
    child: int = _CFB_FREE_SECTOR,
) -> None:
    offset = index * 128
    encoded_name = f"{name}\0".encode("utf-16le")
    if len(encoded_name) > 64:
        raise ValueError(f"CFB directory name is too long: {name}")
    directory[offset : offset + len(encoded_name)] = encoded_name
    pack_into(
        "<HBBIII",
        directory,
        offset + 64,
        len(encoded_name),
        object_type,
        1,
        _CFB_FREE_SECTOR,
        _CFB_FREE_SECTOR,
        child,
    )
    pack_into("<I", directory, offset + 116, _CFB_END_OF_CHAIN)
    pack_into("<Q", directory, offset + 120, 0)


def write_minimal_cfb(
    path: Path,
    extension: str | None = None,
    *,
    stream_name: str | None = None,
) -> Path:
    """Write the smallest CFB container accepted by standard OLE readers."""
    office_stream = stream_name or CFB_STREAM_NAMES[extension or path.suffix.lower()]
    header = bytearray(512)
    header[:8] = bytes.fromhex("D0CF11E0A1B11AE1")
    pack_into("<HHHH", header, 24, 0x003E, 3, 0xFFFE, 9)
    pack_into("<H", header, 32, 6)
    pack_into(
        "<IIIIIIIII",
        header,
        40,
        0,
        1,
        1,
        0,
        4096,
        _CFB_END_OF_CHAIN,
        0,
        _CFB_END_OF_CHAIN,
        0,
    )
    for index in range(109):
        pack_into("<I", header, 76 + 4 * index, _CFB_FREE_SECTOR)
    pack_into("<I", header, 76, 0)

    fat = bytearray(512)
    for index in range(128):
        pack_into("<I", fat, 4 * index, _CFB_FREE_SECTOR)
    pack_into("<I", fat, 0, _CFB_FAT_SECTOR)
    pack_into("<I", fat, 4, _CFB_END_OF_CHAIN)

    directory = bytearray(512)
    _write_cfb_directory_entry(directory, 0, "Root Entry", 5, child=1)
    _write_cfb_directory_entry(directory, 1, office_stream, 2)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + fat + directory)
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
