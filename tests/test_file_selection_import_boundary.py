from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_shared_file_selection_import_is_lightweight_and_does_not_write(tmp_path):
    library = Path(__file__).resolve().parents[1] / "libs" / "ktem"
    probe = """
import importlib.abc
import json
import sys

blocked = {"ktem", "kotaemon", "gradio", "theflow", "llama_index", "torch"}

class RejectRuntimeImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in blocked:
            raise AssertionError("Unexpected runtime import: " + fullname)

sys.meta_path.insert(0, RejectRuntimeImports())
sys.path.insert(0, sys.argv[1])
from ktem_contracts.file_selection import (
    merge_unique_file_ids,
    normalize_selected_file_ids,
)

assert normalize_selected_file_ids([" a ", "a", 0, False]) == [" a ", "a", "0", "False"]
assert merge_unique_file_ids([" a ", "a", 0, False], ("b", "c")) == ["a", "('b', 'c')"]
assert not blocked.intersection(name.split(".")[0] for name in sys.modules)
print(json.dumps({"module": normalize_selected_file_ids.__module__, "runtime_imports": []}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(library)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {
        "module": "ktem_contracts.file_selection",
        "runtime_imports": [],
    }
    assert list(tmp_path.iterdir()) == []
