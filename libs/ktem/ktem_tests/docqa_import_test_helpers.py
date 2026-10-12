"""Run real DocQA imports in a fresh process and an existing owned test runtime."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from pytest_runtime_isolation import ActiveTestRuntime

PROBE_PREAMBLE = """
import importlib
import json
import os
import sys
from pathlib import Path

owned_root = Path(os.environ['MARA_PYTEST_RUNTIME_ROOT']).resolve()
events = []
phase = 'parent'
coverage_file = os.environ.get('COVERAGE_FILE')
coverage_path = Path(coverage_file).resolve() if coverage_file else None

def is_coverage_shutdown_path(path):
    return (
        phase == 'shutdown' and coverage_path is not None
        and (path == coverage_path.parent or (
            path.parent == coverage_path.parent
            and path.name.startswith(coverage_path.name)
        ))
    )

def audit(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise AssertionError('Import attempted network access: ' + event)
    if event == 'sqlite3.connect':
        database = os.fsdecode(args[0])
        if is_coverage_shutdown_path(Path(database).resolve()):
            return
        events.append([phase, event])
        if database != ':memory:':
            assert Path(database).resolve().is_relative_to(owned_root), database
    if event == 'open':
        path, mode, flags = args
        if not isinstance(path, (str, bytes)):
            return
        if not (flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            return
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir'):
        path = args[0]
    else:
        return
    path = Path(os.fsdecode(path)).resolve()
    # The existing CI subprocess collector writes only after this probe ends.
    if is_coverage_shutdown_path(path):
        return
    if os.path.normcase(str(path)) == os.path.normcase(str(Path(os.devnull).resolve())):
        return
    assert path.is_relative_to(owned_root), str(path)
    events.append([phase, event, path.relative_to(owned_root).as_posix()])

sys.addaudithook(audit)
assert 'ktem' not in sys.modules
import ktem
parent_modules = set(sys.modules)
parent_events = list(events)
phase = 'docqa'
"""

PROBE_EPILOGUE = """
result = {
    'parent_modules': sorted(parent_modules),
    'added_modules': sorted(set(sys.modules) - parent_modules),
    'parent_events': parent_events,
    'added_events': events[len(parent_events):],
    'ktem_path': ktem.__file__,
}
print('DOCQA_IMPORT_RESULT=' + json.dumps(result))
phase = 'shutdown'
"""


def run_docqa_import_probe(source: str) -> dict:
    library = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(library), environment.get("PYTHONPATH", "")]
    )
    runtime = ActiveTestRuntime.start(environment)
    try:
        completed = subprocess.run(
            [sys.executable, "-B", "-c", PROBE_PREAMBLE + source + PROBE_EPILOGUE],
            env=environment,
            cwd=runtime.paths.root,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        result = json.loads(
            next(
                line.removeprefix("DOCQA_IMPORT_RESULT=")
                for line in completed.stdout.splitlines()
                if line.startswith("DOCQA_IMPORT_RESULT=")
            )
        )
        assert Path(result["ktem_path"]).resolve() == library / "ktem/__init__.py"
        return result
    finally:
        runtime.close()
        assert not runtime.paths.root.exists()
