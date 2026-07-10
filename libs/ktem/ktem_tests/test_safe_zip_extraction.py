from __future__ import annotations

import stat
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from ktem.docqa import _runtime_indexing
from ktem.index.file.archive import (
    ArchiveExtractionError,
    ArchiveLimits,
    extract_supported_zip_files,
)
from ktem.index.file.ui import FileIndexPage


def _write_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)


def test_safe_zip_extracts_only_supported_regular_files(tmp_path):
    archive_path = tmp_path / "bundle.zip"
    _write_zip(
        archive_path,
        {
            "nested/report.TXT": b"report",
            "nested/ignored.md": b"ignored",
            "nested/again.zip": b"not recursively extracted",
        },
    )

    paths = extract_supported_zip_files(
        archive_path,
        destination_parent=tmp_path / "expanded",
        supported_types={".txt", ".zip"},
    )

    assert len(paths) == 1
    assert Path(paths[0]).relative_to(tmp_path / "expanded").parts[-2:] == (
        "nested",
        "report.TXT",
    )
    assert Path(paths[0]).read_bytes() == b"report"


@pytest.mark.parametrize(
    "member",
    [
        "../outside.txt",
        "nested/../../outside.txt",
        "/absolute.txt",
        r"C:\\absolute.txt",
        r"\\\\server\\share\\outside.txt",
    ],
)
def test_safe_zip_rejects_paths_outside_owned_directory(tmp_path, member):
    archive_path = tmp_path / "malicious.zip"
    _write_zip(archive_path, {member: b"payload", "safe.txt": b"safe"})

    with pytest.raises(ArchiveExtractionError) as exc_info:
        extract_supported_zip_files(
            archive_path,
            destination_parent=tmp_path / "expanded",
            supported_types={".txt"},
        )

    diagnostic = str(exc_info.value)
    assert f"archive={archive_path}" in diagnostic
    assert "stage=validate-member" in diagnostic
    assert "member=" in diagnostic
    assert not (tmp_path / "outside.txt").exists()
    assert not (tmp_path / "expanded").exists()


def test_safe_zip_rejects_symbolic_link_members_before_writing(tmp_path):
    archive_path = tmp_path / "symlink.zip"
    link = zipfile.ZipInfo("link.txt")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(link, "../outside.txt")

    with pytest.raises(ArchiveExtractionError, match="symbolic link"):
        extract_supported_zip_files(
            archive_path,
            destination_parent=tmp_path / "expanded",
            supported_types={".txt"},
        )

    assert not (tmp_path / "expanded").exists()


@pytest.mark.parametrize(
    ("limits", "entries", "reason"),
    [
        (ArchiveLimits(max_members=1), {"a.txt": b"a", "b.txt": b"b"}, "members"),
        (
            ArchiveLimits(max_member_bytes=3),
            {"large.txt": b"four"},
            "member size",
        ),
        (
            ArchiveLimits(max_total_bytes=3),
            {"a.txt": b"aa", "b.txt": b"bb"},
            "total size",
        ),
        (
            ArchiveLimits(max_compression_ratio=2),
            {"compressed.txt": b"0" * 10_000},
            "compression ratio",
        ),
    ],
)
def test_safe_zip_enforces_archive_resource_limits(
    tmp_path,
    limits,
    entries,
    reason,
):
    archive_path = tmp_path / "oversized.zip"
    _write_zip(archive_path, entries)

    with pytest.raises(ArchiveExtractionError, match=reason):
        extract_supported_zip_files(
            archive_path,
            destination_parent=tmp_path / "expanded",
            supported_types={".txt"},
            limits=limits,
        )

    assert not (tmp_path / "expanded").exists()


def test_safe_zip_rejects_corrupt_archives_with_actionable_stage(tmp_path):
    archive_path = tmp_path / "corrupt.zip"
    archive_path.write_bytes(b"not-a-zip")

    with pytest.raises(ArchiveExtractionError) as exc_info:
        extract_supported_zip_files(
            archive_path,
            destination_parent=tmp_path / "expanded",
            supported_types={".txt"},
        )

    diagnostic = str(exc_info.value)
    assert f"archive={archive_path}" in diagnostic
    assert "stage=open" in diagnostic


def test_runtime_zip_expansion_uses_safe_shared_extractor(tmp_path, monkeypatch):
    calls: list[tuple[Path, Path, set[str]]] = []

    def fake_extract(archive_path, *, destination_parent, supported_types):
        calls.append(
            (Path(archive_path), Path(destination_parent), set(supported_types))
        )
        return [str(tmp_path / "expanded/result.txt")]

    monkeypatch.setattr(_runtime_indexing, "extract_supported_zip_files", fake_extract)
    file_index = SimpleNamespace(config={"supported_file_types": ".txt"})
    archive_path = tmp_path / "bundle.zip"
    archive_path.write_bytes(b"placeholder")

    result = _runtime_indexing.expand_zip_inputs(
        file_index,
        [str(archive_path)],
        zip_input_dir=tmp_path / "zip-root",
    )

    assert result == [str(tmp_path / "expanded/result.txt")]
    assert calls == [(archive_path, tmp_path / "zip-root", {".txt"})]


def test_file_index_page_reports_archive_diagnostic_and_keeps_safe_files(
    tmp_path, monkeypatch
):
    page = cast(Any, FileIndexPage.__new__(FileIndexPage))
    page._supported_file_types = [".txt"]
    safe_zip = tmp_path / "safe.zip"
    unsafe_zip = tmp_path / "unsafe.zip"
    plain_file = tmp_path / "plain.txt"
    for path in (safe_zip, unsafe_zip, plain_file):
        path.write_bytes(b"placeholder")

    def fake_extract(archive_path, *, destination_parent, supported_types):
        if Path(archive_path) == unsafe_zip:
            raise ArchiveExtractionError(
                unsafe_zip,
                stage="validate-member",
                reason="path traversal",
                member="../outside.txt",
            )
        return [str(tmp_path / "zip-root/owned/safe.txt")]

    monkeypatch.setattr(file_ui_module(), "extract_supported_zip_files", fake_extract)

    files, errors = page._may_extract_zip(
        [str(safe_zip), str(unsafe_zip), str(plain_file)],
        str(tmp_path / "zip-root"),
    )

    assert files == [
        str(plain_file),
        str(tmp_path / "zip-root/owned/safe.txt"),
    ]
    assert len(errors) == 1
    assert f"archive={unsafe_zip}" in errors[0]
    assert "stage=validate-member" in errors[0]


def file_ui_module():
    import ktem.index.file.ui as module

    return module
