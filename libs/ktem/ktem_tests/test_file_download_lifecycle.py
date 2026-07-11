from __future__ import annotations

import json
import os
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import gradio as gr
import pytest
from ktem.index.file._scoped_page import ScopedFileIndexPageMixin
from ktem.index.file._selection_service import FileSelectionError
from theflow.settings import settings as flowsettings

from kotaemon.artifact_downloads import (
    READY_FETCH_WINDOW_SECONDS,
    READY_OUTPUT_HARD_LIMIT,
    READY_OUTPUT_TTL_SECONDS,
    DownloadWorkspace,
)

FILE_ID = "file-owner"
GENERATION = "generation-a"


class _SelectionService:
    @staticmethod
    def source_name(file_id, user_id):
        if (file_id, user_id) != (FILE_ID, "owner"):
            raise FileSelectionError("source unavailable")
        return "report.pdf"


class _Page(ScopedFileIndexPageMixin):
    @staticmethod
    def _get_file_selection_service():
        return _SelectionService()


@pytest.fixture
def roots(tmp_path, monkeypatch):
    result = SimpleNamespace(
        chunks=tmp_path / "chunks",
        markdown=tmp_path / "markdown",
        zip=tmp_path / "zip",
    )
    for root in vars(result).values():
        root.mkdir()
    monkeypatch.setattr(flowsettings, "MARA_AUTH_MODE", "auto", raising=False)
    monkeypatch.setattr(
        flowsettings, "KH_CHUNKS_OUTPUT_DIR", str(result.chunks), raising=False
    )
    monkeypatch.setattr(
        flowsettings, "KH_MARKDOWN_OUTPUT_DIR", str(result.markdown), raising=False
    )
    monkeypatch.setattr(
        flowsettings, "KH_ZIP_OUTPUT_DIR", str(result.zip), raising=False
    )
    return result


def _prepare_manifest(roots) -> None:
    artifact = roots.chunks / FILE_ID / GENERATION / "report_0.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("OWNER", encoding="utf-8")
    manifest = roots.zip / "manifests" / "v1" / FILE_ID / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "file_id": FILE_ID,
                "entries": [
                    {
                        "kind": "chunks",
                        "relative_path": (f"{FILE_ID}/{GENERATION}/report_0.md"),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _server_download_dirs(roots) -> list[Path]:
    parent = roots.zip / "downloads" / FILE_ID
    return sorted(path for path in parent.iterdir()) if parent.exists() else []


def _ready_workspace(
    root: Path,
    file_id: str,
    request_name: str,
    *,
    marker_age: float = 0,
) -> Path:
    request = root / "downloads" / file_id / request_name
    request.mkdir(parents=True)
    marker = request / ".ready"
    marker.write_text("0", encoding="utf-8")
    (request / "download.html").write_text("READY", encoding="utf-8")
    if marker_age:
        modified = time.time() - marker_age
        os.utime(marker, (modified, modified))
    return request


def test_zip_toggle_off_does_not_create_unreturned_output(roots):
    _prepare_manifest(roots)

    state, button = _Page().download_single_file(True, FILE_ID, "owner")

    assert state is False
    assert button.value is None
    assert _server_download_dirs(roots) == []


def test_simple_html_toggle_off_does_not_create_unreturned_output(roots):
    state, button = _Page().download_single_file_simple(True, "OWNER", FILE_ID, "owner")

    assert state is False
    assert button.value is None
    assert _server_download_dirs(roots) == []


def test_zip_failure_removes_temporary_and_active_request_directory(roots, monkeypatch):
    _prepare_manifest(roots)

    def fail_archive_open(*_args, **_kwargs):
        raise OSError("zip stream failed")

    monkeypatch.setattr(zipfile.ZipFile, "open", fail_archive_open)

    with pytest.raises(gr.Error, match="reindex"):
        _Page().download_single_file(False, FILE_ID, "owner")

    assert _server_download_dirs(roots) == []


def test_cleanup_failure_does_not_override_uniform_download_error(roots, monkeypatch):
    _prepare_manifest(roots)

    def fail_archive_open(*_args, **_kwargs):
        raise OSError("zip stream failed")

    def fail_cleanup(_workspace):
        raise OSError("cleanup failed")

    monkeypatch.setattr(zipfile.ZipFile, "open", fail_archive_open)
    monkeypatch.setattr(DownloadWorkspace, "cleanup", fail_cleanup)

    with pytest.raises(gr.Error, match="reindex"):
        _Page().download_single_file(False, FILE_ID, "owner")


def test_html_replace_failure_removes_temporary_and_active_request_directory(
    roots, monkeypatch
):
    real_replace = os.replace

    def fail_html_replace(source, destination, *args, **kwargs):
        if str(destination).endswith(".html"):
            raise OSError("html replace failed")
        return real_replace(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "replace", fail_html_replace)

    with pytest.raises(gr.Error, match="reindex"):
        _Page().download_single_file_simple(False, "OWNER", FILE_ID, "owner")

    assert _server_download_dirs(roots) == []


def test_pruning_removes_expired_ready_outputs_but_keeps_active_request(roots):
    parent = roots.zip / "downloads" / FILE_ID
    active = parent / "active-request"
    active.mkdir(parents=True)
    (active / ".active").write_text("0", encoding="utf-8")
    for index in range(35):
        ready = parent / f"ready-{index:02d}"
        ready.mkdir()
        marker = ready / ".ready"
        marker.write_text("0", encoding="utf-8")
        (ready / f"download-{index:02d}.html").write_text(
            "EXPIRED",
            encoding="utf-8",
        )
        expired = time.time() - READY_OUTPUT_TTL_SECONDS - 1
        os.utime(marker, (expired, expired))

    _Page().download_single_file_simple(False, "OWNER", FILE_ID, "owner")

    assert active.exists()
    remaining_old = [
        path
        for path in parent.iterdir()
        if path.name.startswith("ready-") and path.exists()
    ]
    assert remaining_old == []


def test_pruning_bounds_valid_ready_payloads_outside_fetch_window(roots):
    parent = roots.zip / "downloads" / FILE_ID
    stale = time.time() - READY_FETCH_WINDOW_SECONDS - 1
    for index in range(35):
        ready = parent / f"stale-{index:02d}"
        ready.mkdir(parents=True)
        marker = ready / ".ready"
        marker.write_text("0", encoding="utf-8")
        (ready / f"download-{index:02d}.html").write_text(
            "STALE",
            encoding="utf-8",
        )
        os.utime(marker, (stale, stale))

    _Page().download_single_file_simple(False, "OWNER", FILE_ID, "owner")

    remaining_old = [
        path
        for path in parent.iterdir()
        if path.name.startswith("stale-") and path.exists()
    ]
    assert len(remaining_old) <= 32


def test_global_pruning_reclaims_expired_ready_output_from_other_file_id(roots):
    expired = _ready_workspace(
        roots.zip,
        "file-other",
        "expired-request",
        marker_age=READY_OUTPUT_TTL_SECONDS + 1,
    )

    _Page().download_single_file_simple(False, "OWNER", FILE_ID, "owner")

    assert not expired.exists()


def test_global_pruning_reclaims_unlocked_stale_active_workspace(roots):
    stale = roots.zip / "downloads" / "file-other" / "stale-active"
    stale.mkdir(parents=True)
    marker = stale / ".active"
    marker.write_text("0", encoding="utf-8")
    (stale / ".download-stale.tmp").write_text("PARTIAL", encoding="utf-8")
    expired = time.time() - READY_OUTPUT_TTL_SECONDS - 1
    os.utime(marker, (expired, expired))

    _Page().download_single_file_simple(False, "OWNER", FILE_ID, "owner")

    assert not stale.exists()


def test_global_pruning_keeps_old_live_active_lease(roots):
    workspace = DownloadWorkspace.create(roots.zip, FILE_ID, ".html")
    marker = workspace.directory / ".active"
    expired = time.time() - READY_OUTPUT_TTL_SECONDS - 1
    os.utime(marker, (expired, expired))

    try:
        _Page().download_single_file_simple(False, "OWNER", FILE_ID, "owner")
        assert workspace.directory.exists()
        assert marker.exists()
    finally:
        workspace.cleanup()


def test_global_capacity_rejects_new_output_without_revoking_fresh_paths(roots):
    existing = [
        _ready_workspace(
            roots.zip,
            f"file-{index:03d}",
            "fresh-request",
        )
        for index in range(READY_OUTPUT_HARD_LIMIT)
    ]

    with pytest.raises(gr.Error, match="reindex"):
        _Page().download_single_file_simple(False, "OWNER", FILE_ID, "owner")

    assert all(path.exists() for path in existing)


def test_ready_output_survives_followup_prune_for_browser_fetch_window(roots):
    first_result = _Page().download_single_file_simple(
        False, "OWNER ONE", FILE_ID, "owner"
    )
    first_value = first_result[1].value
    first_gradio_path = Path(
        first_value["path"] if isinstance(first_value, dict) else first_value
    )
    server_files = list((roots.zip / "downloads" / FILE_ID).rglob("*.html"))
    assert len(server_files) == 1
    first_server_path = server_files[0]
    assert (first_server_path.parent / ".ready").is_file()
    assert not (first_server_path.parent / ".active").exists()

    for index in range(40):
        ready = roots.zip / "downloads" / FILE_ID / f"fresh-{index:02d}"
        ready.mkdir()
        (ready / ".ready").write_text("0", encoding="utf-8")
        (ready / f"download-{index:02d}.html").write_text(
            "FRESH",
            encoding="utf-8",
        )
    _Page().download_single_file_simple(False, "OWNER TWO", FILE_ID, "owner")

    assert first_server_path.read_text(encoding="utf-8") == "OWNER ONE"
    assert first_gradio_path.read_text(encoding="utf-8") == "OWNER ONE"
    assert not list((roots.zip / "downloads" / FILE_ID).rglob("*.tmp"))
