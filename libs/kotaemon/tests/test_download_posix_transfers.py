"""Native POSIX retention/transfer protocol; Windows retains its capability gate."""

import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest

from kotaemon import artifact_transfers as transfers
from kotaemon.artifact_downloads import DownloadWorkspace
from kotaemon.artifact_retention import READY_OUTPUT_TTL_SECONDS
from kotaemon.artifact_transfers import claim_download
from kotaemon.artifact_types import ArtifactNamespaceError

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="native secure dir_fd and flock required"
)
CONTEXT = {"index": "1", "owner": "alice", "source": "generation"}


def _publish(root, content=b"owned"):
    workspace = DownloadWorkspace.create(root, "file", ".html")
    with workspace.open_temporary() as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())
    path = workspace.publish(context=CONTEXT)
    return workspace, path


def test_transfer_lease_survives_expiry_and_closes_before_retention(tmp_path):
    workspace, path = _publish(tmp_path)
    transfer = claim_download(tmp_path, "file", path.parent.name, ".html", CONTEXT)
    marker = path.parent / ".ready"
    expired = time.time() - READY_OUTPUT_TTL_SECONDS - 1
    os.utime(marker, (expired, expired))
    other = DownloadWorkspace.create(tmp_path, "other", ".html")
    assert path.is_file()
    assert os.read(transfer.fd, 50) == b"owned"
    with pytest.raises(ArtifactNamespaceError, match="expired"):
        claim_download(tmp_path, "file", path.parent.name, ".html", CONTEXT)
    transfer.close()
    transfer.close()
    last = DownloadWorkspace.create(tmp_path, "last", ".html")
    assert not workspace.directory.exists()
    other.cleanup()
    last.cleanup()


def test_same_file_concurrent_generations_and_transfers_are_independent(tmp_path):
    def generate(number):
        content = f"owned-{number}".encode()
        _workspace, path = _publish(tmp_path, content)
        transfer = claim_download(tmp_path, "file", path.parent.name, ".html", CONTEXT)
        try:
            assert os.read(transfer.fd, 99) == content
            return path
        finally:
            transfer.close()

    with ThreadPoolExecutor(4) as workers:
        paths = list(workers.map(generate, range(8)))
    assert len(set(paths)) == 8 and all(path.exists() for path in paths)


@pytest.mark.parametrize("failure", ["marker", "active", "sync"])
def test_failed_ready_publication_retains_no_claimable_result(
    tmp_path, monkeypatch, failure
):
    workspace = DownloadWorkspace.create(tmp_path, "file", ".html")
    with workspace.open_temporary() as output:
        output.write(b"owned")
    import kotaemon.artifact_downloads as downloads

    def fail(*args, **kwargs):
        raise OSError("controlled publication failure")

    with monkeypatch.context() as patch:
        if failure == "marker":
            patch.setattr(workspace, "_write_marker", fail)
        elif failure == "active":
            patch.setattr(downloads, "unlink_at", fail)
        else:
            patch.setattr(workspace, "_release_active_lease", fail)
        with pytest.raises(OSError, match="controlled publication"):
            workspace.publish(context=CONTEXT)
    with pytest.raises((ArtifactNamespaceError, OSError)):
        claim_download(tmp_path, "file", workspace.directory.name, ".html", CONTEXT)
    workspace.cleanup()
    assert not workspace.directory.exists()


@pytest.mark.parametrize(
    "receipt",
    [b"{", b"x" * 8193, b'{"owner":"bob"}'],
    ids=["corrupt", "oversized", "foreign_scope"],
)
def test_invalid_ready_receipt_releases_every_claim_descriptor(
    tmp_path, monkeypatch, receipt
):
    _workspace, path = _publish(tmp_path)
    (path.parent / ".ready").write_bytes(receipt)
    open_root, close_fd = transfers.open_directory_fd, os.close
    opened, closed = [], []

    def track_root(*args, **kwargs):
        result = open_root(*args, **kwargs)
        opened.append(result[1])
        return result

    def track_acquisition(operation):
        def acquire(*args, **kwargs):
            fd = operation(*args, **kwargs)
            if fd is not None:
                opened.append(fd)
            return fd

        return acquire

    def track_close(fd):
        close_fd(fd)
        if fd in opened:
            closed.append(fd)

    with monkeypatch.context() as patch:
        patch.setattr(transfers, "open_directory_fd", track_root)
        for name in (
            "open_child_directory",
            "_acquire_lifecycle_lock",
            "_open_regular_entry",
        ):
            patch.setattr(transfers, name, track_acquisition(getattr(transfers, name)))
        patch.setattr(os, "close", track_close)
        with pytest.raises(ArtifactNamespaceError):
            claim_download(tmp_path, "file", path.parent.name, ".html", CONTEXT)
    assert opened and Counter(opened) == Counter(closed)
    for fd in set(opened):
        with pytest.raises(OSError):
            os.fstat(fd)
    assert path.read_bytes() == b"owned"
    assert (path.parent / ".ready").read_bytes() == receipt
