from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pytest_runtime_isolation import activate_test_runtime

REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE = r"""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

root = Path(os.environ["MARA_PYTEST_RUNTIME_ROOT"]).resolve()
null_device = Path(os.devnull).resolve()
denied = []


def audit(event, args):
    paths = []
    if event == "open" and isinstance(args[0], (str, bytes)):
        path, mode, flags = args
        write = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        path = Path(os.fsdecode(path)).resolve()
        if write or path.name in {".env", "flowsettings.py", "settings.ini"}:
            paths = [path]
    elif event in {"os.mkdir", "os.remove", "os.rmdir", "sqlite3.connect"}:
        if isinstance(args[0], (str, bytes)) and args[0] != ":memory:":
            paths = [Path(os.fsdecode(args[0])).resolve()]
    elif event == "os.rename":
        paths = [Path(os.fsdecode(value)).resolve() for value in args[:2]]
    elif event == "socket.connect":
        raise RuntimeError("Probe attempted a network connection")
    for path in paths:
        # subprocess/platform use the OS null device; it stores no file data.
        if path != null_device and not path.is_relative_to(root):
            denied.append({"event": event, "path": str(path)})
            raise RuntimeError("Audit stopped I/O outside the test runtime")


sys.addaudithook(audit)


def probe():
    from theflow.settings import settings
    from theflow.storage import storage
    from ktem.db.engine import engine

    runtime = bootstrap.get_runtime_paths()
    actual = {
        "config": str(runtime.config_dir),
        "data": str(runtime.data_dir),
        "cache": str(runtime.cache_dir),
        "storage": str(storage._prefix),
        "database": str(engine.url.database),
        "files": str(settings.KH_FILESTORAGE_PATH),
        "docstore": str(settings.KH_DOCSTORE["path"]),
        "vectorstore": str(settings.KH_VECTORSTORE["path"]),
        "output": os.environ["MARA_OUTPUT_DIR"],
    }
    assert str(settings.STORAGE["prefix"]) == actual["storage"]
    for path in actual.values():
        assert Path(path).resolve().is_relative_to(root), path
    for name, value in vars(settings).items():
        if name.startswith("KH_") and name.endswith(("_DIR", "_PATH")):
            assert Path(value).resolve().is_relative_to(root), name
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE IF NOT EXISTS canary (id INTEGER)")
    engine.dispose()
    (Path(actual["files"]) / "canary.txt").write_text("session-only")
    (Path(actual["output"]) / "canary.txt").write_text("session-only")

    assert Echo()("canary") == "canary"
    assert any(Path(actual["storage"]).rglob("progress.pkl"))
    assert "MARA_TEST_LEAK" not in os.environ
    assert not denied, denied
    result = {"actual": actual, "source": bootstrap.__file__, "denied": denied}
    if "--leaf" not in sys.argv:
        nested = subprocess.run(
            [sys.executable, __file__, "--leaf"],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        assert nested.returncode == 0, nested.stderr
        result["child"] = json.loads(nested.stdout.strip().splitlines()[-1])
    return result


try:
    if os.environ.get("MARA_TEST_SETTINGS_FIRST") == "1":
        from theflow.settings import settings
        assert settings.STORAGE
    import ktem.runtime_bootstrap as bootstrap
    from theflow import Function

    class Echo(Function):
        def run(self, value):
            return value

    print(json.dumps(probe()))
except RuntimeError as error:
    import traceback
    traceback.print_exc()
    print(json.dumps({"error": str(error), "denied": denied}))
    raise SystemExit(3)
"""


def _controlled_process(tmp_path, configure=None):
    outside = tmp_path / "user-candidate"
    outside.mkdir()
    (outside / ".env").write_text("MARA_TEST_LEAK=loaded\n", encoding="utf-8")
    (outside / "flowsettings.py").write_text(
        "raise AssertionError('external flowsettings loaded')\n", encoding="utf-8"
    )
    environment = dict(os.environ)
    environment.update(
        THEFLOW_SETTINGS_MODULE=str(outside / "flowsettings.py"),
        MARA_DESKTOP_DATA_DIR=str(outside),
        MARA_DESKTOP_CHAT_MODEL="inherited-model",
        GRADIO_ANALYTICS_ENABLED="False",
        PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
        PYTHONPATH=os.pathsep.join(
            str(REPO_ROOT / path)
            for path in ("libs/ktem", "libs/kotaemon", "libs/slide_cli")
        ),
    )
    _, paths = activate_test_runtime(environment, tmp_path / "session")
    if configure:
        configure(environment, paths, outside)
    script = paths.root / "probe.py"
    script.write_text(PROBE, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=outside,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert sorted(path.name for path in outside.iterdir()) == [
        ".env",
        "flowsettings.py",
    ]
    return result, paths


@pytest.mark.parametrize("settings_first", [False, True])
def test_effective_storage_and_writes_are_isolated_in_fresh_processes(
    tmp_path, settings_first
):
    def configure(environment, _paths, _outside):
        environment["MARA_TEST_SETTINGS_FIRST"] = str(int(settings_first))

    result, paths = _controlled_process(tmp_path, configure)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    expected_source = REPO_ROOT / "libs/ktem/ktem/runtime_bootstrap.py"
    for process in (payload, payload["child"]):
        assert Path(process["source"]).resolve() == expected_source.resolve()
        assert process["actual"]["database"] == str(paths.database_path)
        assert process["actual"]["files"] == str(paths.file_storage_path)
        assert process["denied"] == []
    assert payload["actual"] == payload["child"]["actual"]


@pytest.mark.parametrize(
    "name",
    [
        "KH_APP_DATA_DIR",
        "KH_DATABASE",
        "KH_FILESTORAGE_PATH",
        "MARA_OUTPUT_DIR",
        "THEFLOW_TEMP_PATH",
        "MARA_DESKTOP_DATA_DIR",
        "NLTK_DATA",
    ],
)
def test_external_environment_override_is_rejected_before_io(tmp_path, name):
    def configure(environment, _paths, outside):
        value = str(outside / "must-not-exist")
        environment[name] = f"sqlite:///{value}" if name == "KH_DATABASE" else value

    result, _ = _controlled_process(tmp_path, configure)

    assert result.returncode == 3, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert "outside the isolated test runtime" in payload["error"]
    assert payload["denied"] == []  # Production validation, before the audit guard.


@pytest.mark.parametrize("override_file", [".env", "flowsettings.py"])
def test_test_owned_config_cannot_redirect_storage_outside_session(
    tmp_path, override_file
):
    def configure(environment, paths, outside):
        if override_file == ".env":
            environment.pop("KH_APP_DATA_DIR")
            content = f"KH_APP_DATA_DIR={outside / 'must-not-exist'}\n"
        else:
            content = (
                f"KH_DATABASE = {'sqlite:///' + str(outside / 'must-not-exist')!r}\n"
            )
        (paths.root / "config" / override_file).write_text(content, encoding="utf-8")

    result, _ = _controlled_process(tmp_path, configure)

    assert result.returncode == 3, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert "outside the isolated test runtime" in payload["error"]
    assert payload["denied"] == []
