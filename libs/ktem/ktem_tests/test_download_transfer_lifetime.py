"""Transfer and cancellation ownership, distinct from the ready fetch window."""

import os
from types import SimpleNamespace

import pytest
from ktem.index.file import _scoped_page as page_module

from kotaemon import artifact_retention as retention


def test_prune_does_not_unlink_a_ready_payload_with_an_active_transfer(
    tmp_path, monkeypatch
):
    request_fd = os.open(tmp_path / "request-fd", os.O_CREAT | os.O_RDWR, 0o600)
    ready_fd = os.open(tmp_path / "ready-fd", os.O_CREAT | os.O_RDWR, 0o600)
    unlinked = []

    def busy(*args):
        raise BlockingIOError("transfer holds shared marker")

    monkeypatch.setattr(retention, "_entry_exists", lambda *args: False)
    monkeypatch.setattr(retention, "_open_regular_entry", lambda *args: ready_fd)
    monkeypatch.setattr(
        retention,
        "_require_lifecycle_lock",
        lambda: SimpleNamespace(flock=busy, LOCK_EX=1, LOCK_NB=2),
    )
    monkeypatch.setattr(retention.os, "rmdir", lambda *args, **kwargs: None)
    monkeypatch.setattr(retention, "unlink_at", lambda *args: unlinked.append(args))
    try:
        removed = retention._remove_workspace(
            73, "owned", request_fd, retention._ScanBudget(10), known_names=()
        )
        assert not removed
        assert not unlinked
    finally:
        for fd in (ready_fd, request_fd):
            try:
                os.close(fd)
            except OSError:
                pass


@pytest.mark.parametrize("archive", [False, True])
def test_cancelled_generation_releases_its_workspace(monkeypatch, archive):
    class Cancelled(BaseException):
        pass

    released = []

    def cancel():
        raise Cancelled()

    workspace = SimpleNamespace(
        open_temporary=cancel, cleanup=lambda: released.append(True)
    )
    monkeypatch.setattr(
        page_module.DownloadWorkspace, "create", lambda *args: workspace
    )
    monkeypatch.setattr(page_module, "load_manifest_artifacts", lambda *args: [])
    monkeypatch.setattr(
        page_module, "resolve_file_index_user_id", lambda user, request: user
    )

    class Page(page_module.ScopedFileIndexPageMixin):
        def _get_file_selection_service(self):
            return SimpleNamespace(source_name=lambda *args: "owned")

    with pytest.raises(Cancelled):
        if archive:
            Page().download_single_file(False, "file", "owner")
        else:
            Page().download_single_file_simple(False, "HTML", "file", "owner")
    assert released == [True]
