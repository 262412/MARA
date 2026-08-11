from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from ktem.runtime_bootstrap import get_runtime_paths, load_packaged_runtime_env

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EMBEDDING_ENV_NAMES = {
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT",
    "AZURE_OPENAI_ENDPOINT",
    "COHERE_API_KEY",
    "GOOGLE_API_KEY",
    "KH_OLLAMA_URL",
    "LOCAL_MODEL",
    "LOCAL_MODEL_EMBEDDINGS",
    "MISTRAL_API_KEY",
    "OPENAI_API_BASE",
    "OPENAI_API_KEY",
    "OPENAI_CHAT_MODEL",
    "OPENAI_EMBEDDINGS_MODEL",
    "VOYAGE_API_KEY",
}


def test_desktop_runtime_paths_stay_inside_the_desktop_data_root(
    monkeypatch,
    tmp_path,
):
    desktop_root = tmp_path / "MARA"
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(desktop_root))

    paths = get_runtime_paths()

    assert paths.config_dir == (desktop_root / "state" / "config").resolve()
    assert paths.data_dir == (desktop_root / "state" / "runtime").resolve()
    assert paths.cache_dir == (desktop_root / "cache").resolve()
    assert paths.flowsettings_path == paths.config_dir / "flowsettings.py"
    assert paths.env_path == paths.config_dir / ".env"


def test_desktop_owned_embedding_config_overrides_inherited_placeholders(
    monkeypatch,
    tmp_path,
):
    desktop_root = tmp_path / "MARA"
    config_dir = desktop_root / "state" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text(
        "OPENAI_API_KEY=desktop-configured-key\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(desktop_root))
    monkeypatch.setenv("OPENAI_API_KEY", "<YOUR_OPENAI_KEY>")

    load_packaged_runtime_env()

    assert os.environ["OPENAI_API_KEY"] == "desktop-configured-key"


def test_desktop_runtime_does_not_search_the_repository_env(tmp_path) -> None:
    desktop_root = tmp_path / "desktop-data"
    read_only_cwd = tmp_path / "read-only-cwd"
    read_only_cwd.mkdir()
    read_only_cwd.chmod(0o555)
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in EMBEDDING_ENV_NAMES
    }
    environment.update(
        {
            "MARA_DESKTOP_DATA_DIR": str(desktop_root),
            "KH_APP_DATA_DIR": str(desktop_root / "state" / "ktem_app_data"),
            "THEFLOW_SETTINGS_MODULE": "ktem.default_flowsettings",
            "KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED": "1",
            "PYTHONPATH": os.pathsep.join(
                [
                    str(REPOSITORY_ROOT / "libs" / "ktem"),
                    str(REPOSITORY_ROOT / "libs" / "kotaemon"),
                    str(REPOSITORY_ROOT / "libs" / "slide_cli"),
                ]
            ),
        }
    )
    script = """
from theflow.settings import settings

assert settings.KH_EMBEDDINGS == {}, sorted(settings.KH_EMBEDDINGS)
"""
    try:
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=read_only_cwd,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        read_only_cwd.chmod(0o755)

    assert completed.returncode == 0, completed.stderr


def test_desktop_theflow_progress_ignores_read_only_cwd_and_storage_override(
    tmp_path,
):
    desktop_root = tmp_path / "desktop-data"
    config_dir = desktop_root / "state" / "config"
    config_dir.mkdir(parents=True)
    read_only_cwd = tmp_path / "read-only-cwd"
    read_only_cwd.mkdir()
    escaped_storage = read_only_cwd / ".theflow"
    (config_dir / "flowsettings.py").write_text(
        "STORAGE = {\n"
        '    "__type__": "theflow.storage.LocalStorage",\n'
        f'    "prefix": {str(escaped_storage)!r},\n'
        "}\n",
        encoding="utf-8",
    )
    read_only_cwd.chmod(0o555)
    environment = {
        **os.environ,
        "MARA_DESKTOP_DATA_DIR": str(desktop_root),
        "KH_APP_DATA_DIR": str(desktop_root / "state" / "ktem_app_data"),
        "THEFLOW_SETTINGS_MODULE": "ktem.default_flowsettings",
        "KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED": "1",
        "PYTHONPATH": os.pathsep.join(
            [
                str(REPOSITORY_ROOT / "libs" / "ktem"),
                str(REPOSITORY_ROOT / "libs" / "kotaemon"),
                str(REPOSITORY_ROOT / "libs" / "slide_cli"),
            ]
        ),
    }
    script = """
import json
from pathlib import Path

from ktem.runtime_bootstrap import get_runtime_paths
from theflow import Function
from theflow.settings import settings
from theflow.storage import storage


class Echo(Function):
    def run(self, value: str) -> str:
        return value


expected = get_runtime_paths().cache_dir / "theflow"
assert Path(settings.STORAGE["prefix"]).resolve() == expected.resolve()
assert Path(storage._prefix).resolve() == expected.resolve()
assert Echo()("unique-desktop-storage-probe") == "unique-desktop-storage-probe"
files = sorted(
    str(path.relative_to(expected))
    for path in expected.rglob("*")
    if path.is_file()
)
print(json.dumps({"storage": str(expected), "files": files}))
"""
    try:
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=read_only_cwd,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        read_only_cwd.chmod(0o755)

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert Path(payload["storage"]) == desktop_root / "cache" / "theflow"
    assert any(path.endswith("progress.pkl") for path in payload["files"])
    assert any(path.endswith("config.yml") for path in payload["files"])
    assert not escaped_storage.exists()
