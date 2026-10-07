from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_real_chroma_fixture_process_closes_owned_files(tmp_path):
    root = Path(__file__).resolve().parents[1]
    parent = tmp_path / "child-sessions"
    environment = dict(
        os.environ,
        MARA_PYTEST_RUNTIME_PARENT=str(parent),
        PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "libs/kotaemon/tests/test_vectorstore.py::TestChromaVectorStore::test_add",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    assert list(parent.iterdir()) == []
