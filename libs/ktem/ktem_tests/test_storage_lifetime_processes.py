"""Cross-process overlap with explicit barriers, never timing completion order."""

import os
import subprocess
import sys
import time
from contextlib import contextmanager

import pytest

from . import test_shared_storage_integration as fixtures
from .test_shared_storage_integration import _add_source, _source_ids

shared_storage_db = fixtures.shared_storage_db


def wait_marker(path, child):
    deadline = time.monotonic() + 30
    while not path.exists():
        assert child.poll() is None, child.communicate()
        assert time.monotonic() < deadline, str(path)
        time.sleep(0.02)


@contextmanager
def child(database, barriers, operation, file_id, user_id, stored_path="shared.bin"):
    barriers.mkdir()
    (barriers / "upload.bin").write_bytes(b"document")
    process = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-m",
            "ktem_tests.storage_lifetime_process_probe",
            str(database[0].url.database),
            str(database[3]),
            str(barriers),
            operation,
            file_id,
            user_id,
            stored_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
    )
    try:
        yield process
    finally:
        (barriers / "release").write_text("release owned child")
        try:
            output = process.communicate(timeout=35)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
            raise
        assert process.returncode == 0, output


@pytest.mark.parametrize(
    "first,second", [("delete", "delete"), ("publish", "delete"), ("delete", "publish")]
)
def test_process_delete_publish_interleavings(
    shared_storage_db, tmp_path, first, second
):
    if first == "delete":
        _add_source(shared_storage_db, "first", "owner-1")
    if second == "delete":
        _add_source(shared_storage_db, "second", "owner-2")
    one, two = tmp_path / "one", tmp_path / "two"
    with child(shared_storage_db, one, first, "first", "owner-1") as a:
        wait_marker(one / "entered", a)
        with child(shared_storage_db, two, second, "second", "owner-2") as b:
            wait_marker(two / "attempted", b)
            assert not (two / "entered").exists()
            assert not (two / "done").exists()
            assert a.pid != b.pid != os.getpid()
            (one / "release").write_text("go")
            wait_marker(one / "done", a)
            # The first deletion kept the second owner's live reference.
            if (first, second) == ("delete", "delete"):
                assert (shared_storage_db[3] / "shared.bin").read_bytes() == b"document"
            wait_marker(two / "entered", b)
            (two / "release").write_text("go")
            wait_marker(two / "done", b)
    expected = {
        name
        for name, operation in (("first", first), ("second", second))
        if operation == "publish"
    }
    assert _source_ids(shared_storage_db) == expected
    assert (shared_storage_db[3] / "shared.bin").exists() is bool(expected)
    assert not list(shared_storage_db[3].glob("*.quarantine-*"))


def test_different_paths_can_enter_in_separate_processes(shared_storage_db, tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"
    with child(shared_storage_db, one, "hold", "first", "owner-1", "first.bin") as a:
        wait_marker(one / "entered", a)
        with child(
            shared_storage_db, two, "hold", "second", "owner-2", "second.bin"
        ) as b:
            wait_marker(two / "entered", b)
            assert not (one / "release").exists()
