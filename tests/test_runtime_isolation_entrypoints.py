from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pytest_runtime_isolation import activate_test_runtime

REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE = """
import json
import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine

fixture_engines = []

@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    value = os.environ.get("MARA_PYTEST_RUNTIME_ROOT")
    assert value, "package pytest did not activate runtime isolation"
    root = Path(value)
    assert root.is_relative_to(Path(os.environ["MARA_PYTEST_RUNTIME_PARENT"]))
    assert Path(config.option.basetemp).is_relative_to(root)
    from ktem.runtime_bootstrap import get_runtime_paths
    from theflow.settings import settings
    actual = get_runtime_paths()
    assert actual.cache_dir.is_relative_to(root)
    assert Path(settings.STORAGE["prefix"]).is_relative_to(root)
    engine = create_engine(f"sqlite:///{root / 'fixture.sqlite'}")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE owned (id INTEGER)")
    fixture_engines.append(engine)  # Keep the fixture pool alive until teardown.
    print("ISOLATED_SESSION=" + json.dumps(str(root)))
"""


@pytest.mark.parametrize(
    "package,test_file",
    [
        ("kotaemon", "test_workspace_flowsettings_storage.py"),
        ("slide_cli", "test_product_metadata.py"),
    ],
)
def test_package_working_directory_activates_and_cleans_runtime(
    tmp_path, package, test_file
):
    environment = dict(os.environ)
    activate_test_runtime(environment, tmp_path / "bootstrap")
    environment.pop("MARA_PYTEST_RUNTIME_ROOT")
    environment.update(
        MARA_PYTEST_RUNTIME_PARENT=str(tmp_path / "sessions"),
        HOME=str(tmp_path / "profile"),
        USERPROFILE=str(tmp_path / "profile"),
        APPDATA=str(tmp_path / "profile/config"),
        LOCALAPPDATA=str(tmp_path / "profile/data"),
        PYTHONIOENCODING="utf-8",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PYTHONPATH=os.pathsep.join(
            str(path)
            for path in (
                tmp_path,
                REPO_ROOT,
                REPO_ROOT / "libs/ktem",
                REPO_ROOT / "libs/kotaemon",
                REPO_ROOT / "libs/slide_cli",
            )
        ),
    )
    (tmp_path / "entrypoint_probe.py").write_text(PROBE, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-s",
            "-p",
            "entrypoint_probe",
            f"tests/{test_file}",
        ],
        cwd=REPO_ROOT / "libs" / package,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    marker = next(
        line
        for line in result.stdout.splitlines()
        if line.startswith("ISOLATED_SESSION=")
    )
    runtime_root = Path(json.loads(marker.split("=", 1)[1]))
    assert not runtime_root.exists()
