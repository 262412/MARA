import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_PYTHONPATH = os.pathsep.join(
    str(REPOSITORY_ROOT / path) for path in ("libs/kotaemon", "libs/ktem")
)


def test_app_doctor_workspace_settings_do_not_create_source_theflow(tmp_path):
    workspace = tmp_path / "workspace"
    home_dir = tmp_path / "home"
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    cache_dir = tmp_path / "cache"
    runtime_dir = tmp_path / "runtime"
    for path in (workspace, home_dir, config_dir, data_dir, cache_dir, runtime_dir):
        path.mkdir()
    shutil.copy2(REPOSITORY_ROOT / "flowsettings.py", workspace / "flowsettings.py")

    environment = os.environ.copy()
    environment.pop("THEFLOW_SETTINGS_MODULE", None)
    environment.pop("KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED", None)
    environment.update(
        {
            "HOME": str(home_dir),
            "USERPROFILE": str(home_dir),
            "APPDATA": str(config_dir),
            "LOCALAPPDATA": str(data_dir),
            "XDG_CONFIG_HOME": str(config_dir),
            "XDG_DATA_HOME": str(data_dir),
            "XDG_CACHE_HOME": str(cache_dir),
            "MARA_RUNTIME_DIR": str(runtime_dir),
            "KH_APP_DATA_DIR": str(runtime_dir / "ktem_app_data"),
            "PYTHONPATH": SOURCE_PYTHONPATH,
        }
    )

    result = subprocess.run(
        [sys.executable, "-m", "kotaemon.cli", "app", "doctor", "--json"],
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["settings_source"] == "workspace-flowsettings"
    assert not (workspace / ".theflow").exists()
    assert (cache_dir / "Kotaemon" / "theflow").is_dir()
