"""Separate native Windows/non-main worker and POSIX main-thread signal receipts."""

import json
import os
import subprocess
import sys


def _run_owned_child(mechanism):
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "ktem_tests.route_stage_process_contracts",
            mechanism,
        ],
        capture_output=True,
        text=True,
        timeout=20,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    record = json.loads(completed.stdout.splitlines()[-1])
    assert record["platform"] == sys.platform and record["mechanism"] == mechanism
    return record


def test_real_platform_mechanisms_in_exclusive_subprocesses():
    worker = _run_owned_child("worker")
    assert len(worker["records"]) == 6
    assert all(row["owned_workers_joined"] == 1 for row in worker["records"])
    receipts = [worker]
    if sys.platform.startswith("linux"):
        signals = _run_owned_child("signal")
        assert len(signals["records"]) == 5
        receipts.append(signals)
    # This is an explicit platform matrix, not a skip or a Windows signal pass.
    print("R4C_NATIVE_PLATFORM " + json.dumps(receipts, sort_keys=True))
