"""Cross-process real-store write/delete overlap, with bounded owned barriers."""

import json
import os
import subprocess
import sys
import threading
from contextlib import contextmanager

import pytest

from . import indexing_backend_test_support as support
from .test_source_write_coordination import capture, coordinator
from .test_storage_lifetime_processes import wait_marker

backend = support.backend


@contextmanager
def producer(root, stage):
    barriers = root / "barriers"
    barriers.mkdir()
    process = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-m",
            "ktem_tests.source_write_process_probe",
            str(root),
            stage,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
    )
    try:
        yield process, barriers
    finally:
        (barriers / "release").write_text("release owned producer")
        try:
            output = process.communicate(timeout=35)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
            raise
        assert process.returncode == 0, output


@pytest.mark.parametrize("stage", ["embedding", "vector"])
def test_cross_process_producer_and_delete_share_the_same_source_lease(
    backend, monkeypatch, tmp_path, stage
):
    backend.source.write_text("processunique input", encoding="utf-8")
    deleter = coordinator(backend)
    original = deleter._gather_plan
    plans = []
    attempted, deleted = threading.Event(), threading.Event()
    errors: list[BaseException] = []

    def gather(*args):
        plan = original(*args)
        plans.append(plan)
        attempted.set()
        return plan

    monkeypatch.setattr(deleter, "_gather_plan", gather)
    with producer(tmp_path, stage) as (process, barriers):
        wait_marker(barriers / "blocked", process)
        file_id = support.rows(backend, "Source")[0].id

        def delete():
            deleter.delete(file_id, user_id="alice")
            deleted.set()

        worker = threading.Thread(target=capture, args=(errors, delete))
        try:
            worker.start()
            assert attempted.wait(10)
            if stage == "embedding":
                assert deleted.wait(10)
            else:
                assert not deleted.is_set()
                assert plans[0].vector_ids == ()
        finally:
            (barriers / "release").write_text("resume producer")
            worker.join(20)
            assert not worker.is_alive()
    assert not errors and deleted.is_set()
    outcome = json.loads((barriers / "result.json").read_text())
    if stage == "embedding":
        assert outcome["status"] == "rejected"
    else:
        assert plans[1].vector_ids
    assert support.rows(backend, "Source") == []
    assert support.rows(backend, "Index") == []
    assert backend.vectors._collection.get()["ids"] == []
    assert backend.documents.query("processunique") == []
    assert not (backend.resources["FileStoragePath"] / plans[0].stored_path).exists()
