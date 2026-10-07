from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module", ["kotaemon.indices.rankings", "ktem.index.file.pipelines"]
)
def test_import_does_not_load_remote_tokenizer_data(module):
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        str(path)
        for path in (
            root,
            root / "libs/kotaemon",
            root / "libs/ktem",
        )
    )
    code = """
import importlib
import sys
from unittest.mock import patch

import pytest_runtime_plugin

with patch('tiktoken.encoding_for_model', side_effect=AssertionError('eager tokenizer')):
    with patch('tiktoken.get_encoding', side_effect=AssertionError('eager tokenizer')):
        importlib.import_module(sys.argv[1])
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, module],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
