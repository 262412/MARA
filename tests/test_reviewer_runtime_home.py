import importlib.util
import sys
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "libs/ktem/ktem/runtime_bootstrap.py"
SPEC = importlib.util.spec_from_file_location("reviewer_runtime_paths", MODULE)
assert SPEC is not None and SPEC.loader is not None
runtime = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runtime
SPEC.loader.exec_module(runtime)
get_runtime_paths = runtime.get_runtime_paths


@pytest.fixture(autouse=True)
def isolated_runtime_environment(monkeypatch):
    monkeypatch.setattr(runtime.os, "environ", {})


def test_reviewer_app_home_isolated_from_existing_user_data(monkeypatch, tmp_path):
    monkeypatch.delenv("MARA_DESKTOP_DATA_DIR", raising=False)
    monkeypatch.setenv("MARA_APP_HOME", str(tmp_path / "reviewer"))

    paths = get_runtime_paths()

    assert paths.config_dir == tmp_path / "reviewer" / "config"
    assert paths.data_dir == tmp_path / "reviewer" / "data"
    assert paths.cache_dir == tmp_path / "reviewer" / "cache"
    assert paths.env_path == paths.config_dir / ".env"
    assert paths.flowsettings_path == paths.config_dir / "flowsettings.py"


def test_desktop_shares_explicit_app_home_with_web_and_cli(monkeypatch, tmp_path):
    monkeypatch.setenv("MARA_APP_HOME", str(tmp_path / "reviewer"))
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(tmp_path / "desktop"))

    paths = get_runtime_paths()
    assert paths.data_dir == tmp_path / "reviewer" / "data"
    assert paths.config_dir == tmp_path / "reviewer" / "config"


def test_desktop_without_shared_profile_keeps_its_independent_data(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(tmp_path / "desktop"))
    assert get_runtime_paths().data_dir == tmp_path / "desktop" / "state" / "runtime"


def test_unset_app_home_preserves_platform_defaults(monkeypatch):
    monkeypatch.delenv("MARA_APP_HOME", raising=False)
    monkeypatch.delenv("MARA_DESKTOP_DATA_DIR", raising=False)
    from platformdirs import PlatformDirs

    expected = PlatformDirs(appname="Kotaemon", appauthor="Cinnamon")
    assert get_runtime_paths().data_dir == Path(expected.user_data_dir).resolve()


def test_test_runtime_keeps_priority_over_external_app_home(monkeypatch, tmp_path):
    owned_root = tmp_path / "test-session"
    owned_root.mkdir()
    external_home = tmp_path / "real-user"
    monkeypatch.setenv("MARA_PYTEST_RUNTIME_ROOT", str(owned_root))
    monkeypatch.setenv("MARA_APP_HOME", str(external_home))

    paths = get_runtime_paths()

    assert paths.data_dir == owned_root / "ktem_app_data"
    assert paths.config_dir == owned_root / "config"
    assert paths.cache_dir == owned_root / "cache"
    assert not external_home.exists()


def test_explicit_profile_bootstrap_ignores_workspace_configuration(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("MARA_APP_HOME", str(tmp_path / "shared"))
    monkeypatch.setattr(runtime, "_prepare_test_configuration", lambda: None)
    monkeypatch.setattr(runtime, "ensure_llama_index_nltk_cache", lambda: None)
    monkeypatch.setattr(
        runtime, "find_local_flowsettings", lambda: tmp_path / "flowsettings.py"
    )
    loaded: list[str] = []
    monkeypatch.setattr(runtime, "_synchronize_theflow_settings", loaded.append)

    assert runtime.bootstrap_runtime_settings() == runtime.PACKAGE_FLOWSETTINGS_MODULE
    assert loaded == [runtime.PACKAGE_FLOWSETTINGS_MODULE]
    assert runtime.describe_runtime_settings()["settings_source"] == "package-default"
