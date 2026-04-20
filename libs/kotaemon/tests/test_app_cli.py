import os
import subprocess
import sys
from pathlib import Path

from kotaemon.cli import _extract_json_payload


def _package_mode_env(tmp_path):
    home_dir = tmp_path / "home"
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    cache_dir = tmp_path / "cache"
    for path in (home_dir, config_dir, data_dir, cache_dir):
        path.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.pop("THEFLOW_SETTINGS_MODULE", None)
    env["HOME"] = str(home_dir)
    env["USERPROFILE"] = str(home_dir)
    env["APPDATA"] = str(config_dir)
    env["LOCALAPPDATA"] = str(data_dir)
    env["XDG_CONFIG_HOME"] = str(config_dir)
    env["XDG_DATA_HOME"] = str(data_dir)
    env["XDG_CACHE_HOME"] = str(cache_dir)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run_package_mode_cli(tmp_path, *args):
    return subprocess.run(
        [sys.executable, "-m", "kotaemon.cli", *args],
        cwd=str(tmp_path),
        env=_package_mode_env(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_docqa_doctor_runs_outside_repo(tmp_path):
    result = _run_package_mode_cli(tmp_path, "docqa", "doctor", "--json")

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    payload = _extract_json_payload(result.stdout)
    assert payload["ok"] is True
    assert payload["index_name"] == "File Collection"


def test_app_doctor_runs_outside_repo(tmp_path):
    result = _run_package_mode_cli(tmp_path, "app", "doctor", "--json")

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    payload = _extract_json_payload(result.stdout)
    assert payload["settings_source"] == "package-default"
    assert Path(payload["app_data_dir"]).exists()
    assert Path(payload["file_storage_path"]).exists()


def test_app_init_writes_user_config_files(tmp_path):
    result = _run_package_mode_cli(tmp_path, "app", "init", "--force", "--json")

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    payload = _extract_json_payload(result.stdout)
    assert Path(payload["config_dir"]).exists()
    assert Path(payload["flowsettings_path"]).exists()
    assert Path(payload["env_path"]).exists()
    assert Path(payload["env_example_path"]).exists()
