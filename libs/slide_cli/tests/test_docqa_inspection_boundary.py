"""The inspection owner is cold and legacy entry adapters remain patchable."""

import json
import os
import subprocess
import sys
from pathlib import Path

from pytest_runtime_isolation import activate_test_runtime


def test_inspection_import_is_inert_and_has_no_reverse_facade_dependency(tmp_path):
    env = os.environ.copy()
    _, paths = activate_test_runtime(env, tmp_path / "cold")
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    code = """
import json, os, sys
before = dict(os.environ)
import slide_cli.docqa_inspection
prefixes = ('click', 'gradio', 'sqlmodel', 'sqlalchemy', 'theflow', 'ktem',
            'kotaemon', 'slide_cli.docqa_runtime')
loaded = [n for n in sys.modules if any(n == p or n.startswith(p + '.') for p in prefixes)]
print(json.dumps({'loaded': loaded, 'environment_unchanged': before == dict(os.environ)}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"loaded": [], "environment_unchanged": True}
    assert not paths.database_path.exists()


def test_legacy_imports_and_cli_patch_consumer(monkeypatch):
    from slide_cli import docqa_cli, docqa_inspection, docqa_runtime

    for name in (
        "collect_docqa_doctor_payload",
        "collect_docqa_file_records",
        "collect_docqa_session_summaries",
        "_resolve_default_user_id",
    ):
        assert getattr(docqa_runtime, name) is getattr(docqa_inspection, name)
    for name in (
        "collect_docqa_doctor_payload",
        "collect_docqa_file_records",
        "collect_docqa_session_summaries",
    ):
        sentinel = object()
        monkeypatch.setattr(docqa_runtime, name, lambda: sentinel)
        assert getattr(docqa_cli, name)() is sentinel


def test_sidecar_still_resolves_legacy_collector_patch_in_a_fresh_process():
    repo = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo / "apps/desktop"), str(repo / "libs/slide_cli")]
    )
    code = """
import json
from unittest.mock import patch
from sidecar.application import DesktopApplicationService
with patch('slide_cli.docqa_runtime.collect_docqa_session_summaries', return_value=[{'name': 'patched'}]):
    print(json.dumps(DesktopApplicationService().list_sessions()))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [{"name": "patched"}]
