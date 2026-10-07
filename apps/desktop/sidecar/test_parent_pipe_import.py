"""The live parent pipe must not block a cold native dependency import."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

CHILD = """
import sys, threading, time
from pathlib import Path
from types import SimpleNamespace
from sidecar.server import _watch_parent_pipe
server = SimpleNamespace(should_exit=False)
watcher = threading.Thread(target=_watch_parent_pipe, args=(server,), daemon=True)
watcher.start()
time.sleep(0.1)
import numpy
Path(sys.argv[1]).write_text('imported while parent remains connected')
watcher.join(timeout=20)
assert not watcher.is_alive() and server.should_exit
"""


@pytest.mark.parametrize("heartbeat", [b"", b"parent-alive\n"])
def test_parent_pipe_allows_cold_native_import_and_still_closes_on_eof(
    tmp_path, heartbeat
):
    env = os.environ.copy()
    repo = Path(__file__).resolve().parents[3]
    env["PYTHONPATH"] = str(repo / "apps/desktop")
    marker = tmp_path / "imported.txt"
    with (tmp_path / "child.log").open("w+", encoding="utf-8") as log:
        child = subprocess.Popen(
            [sys.executable, "-B", "-c", CHILD, str(marker)],
            cwd=tmp_path,
            env=env,
            stdin=subprocess.PIPE,
            stdout=log,
            stderr=log,
        )
        try:
            assert child.stdin is not None
            child.stdin.write(heartbeat)
            child.stdin.flush()
            deadline = time.monotonic() + 10
            while not marker.exists() and child.poll() is None:
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.02)
            imported_before_eof = marker.exists()
        finally:
            assert child.stdin is not None
            child.stdin.close()
            child.wait(timeout=30)
        log.seek(0)
        output = log.read()
    assert child.returncode == 0, output
    assert imported_before_eof, "Native import stalled until the parent pipe closed."
