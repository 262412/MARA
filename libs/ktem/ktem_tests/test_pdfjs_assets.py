from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import socket
import stat
import zipfile
from collections.abc import Mapping
from pathlib import Path

import pytest
from ktem.assets.pdfjs_assets import (
    PDFJS_ARCHIVE_NAME,
    PDFJS_ARCHIVE_SHA256,
    PDFJS_RELEASE_URL,
    PDFJS_RUNTIME_FILE_SHA256,
    PDFJS_VERSION,
    PDFJS_VERSION_DIST,
    PdfJsAssetError,
    _materialize_pdfjs_archive,
    materialize_pdfjs,
    rollback_pdfjs_materialization,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_archive(path: Path, entries: Mapping[str, bytes | str]) -> str:
    with zipfile.ZipFile(path, "w") as archive:
        for name, contents in entries.items():
            archive.writestr(name, contents)
    return _sha256(path)


def _write_valid_archive(path: Path) -> str:
    return _write_archive(
        path,
        {
            "LICENSE": "Apache License\n",
            "build/pdf.mjs": "export const version = 'test';\n",
            "web/viewer.html": "<!doctype html><title>PDF.js</title>\n",
        },
    )


def _destination(app_data_dir: Path) -> Path:
    return app_data_dir / "assets" / "pdfjs" / PDFJS_VERSION


def test_vendored_pdfjs_manifest_and_archive_match_official_release():
    vendor_dir = (
        Path(__file__).resolve().parents[1] / "ktem" / "assets" / "vendor" / "pdfjs"
    )
    manifest_path = vendor_dir / "manifest.json"
    archive_path = vendor_dir / PDFJS_ARCHIVE_NAME
    license_path = vendor_dir / "LICENSE.pdfjs"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert PDFJS_RELEASE_URL == (
        "https://github.com/mozilla/pdf.js/releases/download/v6.1.200/"
        "pdfjs-6.1.200-dist.zip"
    )
    assert manifest == {
        "archive": PDFJS_ARCHIVE_NAME,
        "license": "LICENSE.pdfjs",
        "release_url": PDFJS_RELEASE_URL,
        "runtime_files": PDFJS_RUNTIME_FILE_SHA256,
        "sha256": PDFJS_ARCHIVE_SHA256,
        "upstream": "https://github.com/mozilla/pdf.js",
        "version": PDFJS_VERSION,
        "version_dist": PDFJS_VERSION_DIST,
    }
    assert _sha256(archive_path) == PDFJS_ARCHIVE_SHA256
    assert license_path.read_bytes() == zipfile.ZipFile(archive_path).read("LICENSE")
    with zipfile.ZipFile(archive_path) as archive:
        assert "LICENSE" in archive.namelist()
        assert "web/viewer.html" in archive.namelist()


def test_materialization_is_offline_atomic_and_idempotent(monkeypatch, tmp_path):
    archive_path = tmp_path / "valid.zip"
    archive_sha256 = _write_valid_archive(archive_path)
    app_data_dir = tmp_path / "app-data"

    def _network_forbidden(*_args, **_kwargs):
        raise AssertionError("PDF.js materialization attempted network access")

    monkeypatch.setattr(socket, "create_connection", _network_forbidden)
    first = _materialize_pdfjs_archive(
        archive_path=archive_path,
        expected_sha256=archive_sha256,
        app_data_dir=app_data_dir,
    )
    viewer = first.path / "web" / "viewer.html"
    first_inode = viewer.stat().st_ino
    first_mtime = viewer.stat().st_mtime_ns

    second = _materialize_pdfjs_archive(
        archive_path=archive_path,
        expected_sha256=archive_sha256,
        app_data_dir=app_data_dir,
    )

    assert first.path == _destination(app_data_dir)
    assert first.created is True
    assert second.path == first.path
    assert second.created is False
    assert viewer.stat().st_ino == first_inode
    assert viewer.stat().st_mtime_ns == first_mtime
    marker = json.loads((first.path / ".mara-pdfjs.json").read_text(encoding="utf-8"))
    assert marker == {
        "files": {
            "build/pdf.mjs": _sha256(first.path / "build" / "pdf.mjs"),
            "web/viewer.html": _sha256(first.path / "web" / "viewer.html"),
        },
        "sha256": archive_sha256,
        "version": PDFJS_VERSION,
        "version_dist": PDFJS_VERSION_DIST,
    }
    assert not list(first.path.parent.glob(f".{PDFJS_VERSION}.*"))


def test_packaged_materializer_uses_only_kh_app_data_dir(monkeypatch, tmp_path):
    app_data_dir = tmp_path / "isolated-app-data"
    monkeypatch.setenv("KH_APP_DATA_DIR", str(app_data_dir))
    monkeypatch.chdir(tmp_path)

    result = materialize_pdfjs()

    assert result.path == _destination(app_data_dir).resolve()
    assert (result.path / "web" / "viewer.html").is_file()
    assert not (tmp_path / "libs").exists()


def test_hash_mismatch_is_actionable_and_leaves_no_destination(tmp_path):
    archive_path = tmp_path / "tampered.zip"
    _write_valid_archive(archive_path)
    app_data_dir = tmp_path / "app-data"

    with pytest.raises(PdfJsAssetError, match="SHA-256 mismatch.*expected.*actual"):
        _materialize_pdfjs_archive(
            archive_path=archive_path,
            expected_sha256="0" * 64,
            app_data_dir=app_data_dir,
        )

    assert not _destination(app_data_dir).exists()


@pytest.mark.parametrize(
    "malicious_name",
    [
        "../escaped.txt",
        "web/../../escaped.txt",
        "/absolute.txt",
        r"C:\\absolute.txt",
        r"web\\..\\escaped.txt",
    ],
)
def test_rejects_traversal_and_absolute_archive_members(tmp_path, malicious_name):
    archive_path = tmp_path / "malicious.zip"
    archive_sha256 = _write_archive(
        archive_path,
        {
            "LICENSE": "license",
            "web/viewer.html": "viewer",
            malicious_name: "payload",
        },
    )
    app_data_dir = tmp_path / "app-data"

    with pytest.raises(PdfJsAssetError, match="unsafe PDF.js archive member"):
        _materialize_pdfjs_archive(
            archive_path=archive_path,
            expected_sha256=archive_sha256,
            app_data_dir=app_data_dir,
        )

    assert not _destination(app_data_dir).exists()
    assert not (tmp_path / "escaped.txt").exists()


def test_rejects_symlink_archive_member(tmp_path):
    archive_path = tmp_path / "symlink.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("LICENSE", "license")
        archive.writestr("web/viewer.html", "viewer")
        symlink = zipfile.ZipInfo("web/viewer-link")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(symlink, "viewer.html")

    with pytest.raises(PdfJsAssetError, match="symbolic link"):
        _materialize_pdfjs_archive(
            archive_path=archive_path,
            expected_sha256=_sha256(archive_path),
            app_data_dir=tmp_path / "app-data",
        )


@pytest.mark.parametrize(
    "missing_name",
    ["LICENSE", "build/pdf.mjs", "web/viewer.html"],
)
def test_rejects_archive_missing_required_files(tmp_path, missing_name):
    entries = {
        "LICENSE": "license",
        "build/pdf.mjs": "build",
        "web/viewer.html": "viewer",
    }
    del entries[missing_name]
    archive_path = tmp_path / "missing.zip"
    archive_sha256 = _write_archive(archive_path, entries)

    with pytest.raises(PdfJsAssetError, match=f"missing required file.*{missing_name}"):
        _materialize_pdfjs_archive(
            archive_path=archive_path,
            expected_sha256=archive_sha256,
            app_data_dir=tmp_path / "app-data",
        )


def test_rejects_corrupt_zip_with_actionable_error(tmp_path):
    archive_path = tmp_path / "corrupt.zip"
    archive_path.write_bytes(b"not a zip archive")

    with pytest.raises(PdfJsAssetError, match="not a valid ZIP archive"):
        _materialize_pdfjs_archive(
            archive_path=archive_path,
            expected_sha256=_sha256(archive_path),
            app_data_dir=tmp_path / "app-data",
        )


def test_extraction_failure_removes_partial_temporary_directory(
    monkeypatch,
    tmp_path,
):
    archive_path = tmp_path / "valid.zip"
    archive_sha256 = _write_valid_archive(archive_path)
    app_data_dir = tmp_path / "app-data"

    def _fail_copy(*_args, **_kwargs):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr("ktem.assets.pdfjs_assets.shutil.copyfileobj", _fail_copy)

    with pytest.raises(PdfJsAssetError, match="extract.*synthetic disk failure"):
        _materialize_pdfjs_archive(
            archive_path=archive_path,
            expected_sha256=archive_sha256,
            app_data_dir=app_data_dir,
        )

    assert not _destination(app_data_dir).exists()
    pdfjs_parent = _destination(app_data_dir).parent
    assert not pdfjs_parent.exists() or not list(pdfjs_parent.iterdir())


def test_marker_write_failure_is_actionable_and_removes_partial_directory(
    monkeypatch,
    tmp_path,
):
    archive_path = tmp_path / "valid.zip"
    archive_sha256 = _write_valid_archive(archive_path)
    app_data_dir = tmp_path / "app-data"
    real_write_text = Path.write_text

    def _fail_marker(self, *args, **kwargs):
        if self.name == ".mara-pdfjs.json":
            raise OSError("synthetic read-only filesystem")
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _fail_marker)

    with pytest.raises(
        PdfJsAssetError,
        match="write PDF.js runtime marker.*read-only filesystem",
    ):
        _materialize_pdfjs_archive(
            archive_path=archive_path,
            expected_sha256=archive_sha256,
            app_data_dir=app_data_dir,
        )

    assert not _destination(app_data_dir).exists()
    assert not list(_destination(app_data_dir).parent.iterdir())


def test_existing_corrupt_destination_is_preserved_and_rejected(tmp_path):
    archive_path = tmp_path / "valid.zip"
    archive_sha256 = _write_valid_archive(archive_path)
    destination = _destination(tmp_path / "app-data")
    destination.mkdir(parents=True)
    sentinel = destination / "operator-file.txt"
    sentinel.write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(
        PdfJsAssetError,
        match="runtime directory is incomplete or corrupt.*MARA app init",
    ):
        _materialize_pdfjs_archive(
            archive_path=archive_path,
            expected_sha256=archive_sha256,
            app_data_dir=tmp_path / "app-data",
        )

    assert sentinel.read_text(encoding="utf-8") == "do not overwrite"


def test_existing_destination_with_tampered_viewer_is_rejected(tmp_path):
    archive_path = tmp_path / "valid.zip"
    archive_sha256 = _write_valid_archive(archive_path)
    app_data_dir = tmp_path / "app-data"
    result = _materialize_pdfjs_archive(
        archive_path=archive_path,
        expected_sha256=archive_sha256,
        app_data_dir=app_data_dir,
    )
    (result.path / "web" / "viewer.html").write_text(
        "<script>window.tampered = true</script>",
        encoding="utf-8",
    )

    with pytest.raises(
        PdfJsAssetError,
        match="content hash mismatch.*web/viewer.html",
    ):
        _materialize_pdfjs_archive(
            archive_path=archive_path,
            expected_sha256=archive_sha256,
            app_data_dir=app_data_dir,
        )


@pytest.mark.parametrize(
    "race_error",
    [
        FileExistsError(errno.EEXIST, "publisher exists"),
        OSError(errno.ENOTEMPTY, "publisher directory not empty"),
    ],
    ids=["eexist", "enotempty"],
)
def test_concurrent_publisher_revalidates_winner_and_cleans_loser(
    monkeypatch,
    tmp_path,
    race_error,
):
    archive_path = tmp_path / "valid.zip"
    archive_sha256 = _write_valid_archive(archive_path)
    app_data_dir = tmp_path / "app-data"
    real_rename = os.rename
    raced = False

    def _publish_other_process_then_fail(source, destination):
        nonlocal raced
        if not raced and Path(source).name.startswith(f".{PDFJS_VERSION}."):
            raced = True
            shutil.copytree(source, destination)
            raise race_error
        return real_rename(source, destination)

    monkeypatch.setattr(
        "ktem.assets.pdfjs_assets.os.rename", _publish_other_process_then_fail
    )

    result = _materialize_pdfjs_archive(
        archive_path=archive_path,
        expected_sha256=archive_sha256,
        app_data_dir=app_data_dir,
    )

    assert raced is True
    assert result.path == _destination(app_data_dir)
    assert result.created is False
    assert (result.path / "web" / "viewer.html").is_file()
    assert not list(result.path.parent.glob(f".{PDFJS_VERSION}.*"))


def test_rollback_filesystem_failure_is_actionable(monkeypatch, tmp_path):
    materialization = materialize_pdfjs(app_data_dir=tmp_path / "app-data")

    def _fail_remove(*_args, **_kwargs):
        raise OSError("synthetic busy destination")

    monkeypatch.setattr("ktem.assets.pdfjs_assets.shutil.rmtree", _fail_remove)

    with pytest.raises(PdfJsAssetError, match="roll back PDF.js.*busy destination"):
        rollback_pdfjs_materialization(materialization)


def test_rejects_symlinked_assets_parent_that_escapes_app_data(tmp_path):
    archive_path = tmp_path / "valid.zip"
    archive_sha256 = _write_valid_archive(archive_path)
    app_data_dir = tmp_path / "app-data"
    outside = tmp_path / "outside"
    app_data_dir.mkdir()
    outside.mkdir()
    (app_data_dir / "assets").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PdfJsAssetError, match="must remain below KH_APP_DATA_DIR"):
        _materialize_pdfjs_archive(
            archive_path=archive_path,
            expected_sha256=archive_sha256,
            app_data_dir=app_data_dir,
        )

    assert not (outside / "pdfjs").exists()
