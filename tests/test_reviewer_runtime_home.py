import importlib.util
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "libs/ktem/ktem/runtime_bootstrap.py"
SPEC = importlib.util.spec_from_file_location("reviewer_runtime_paths", MODULE)
assert SPEC is not None and SPEC.loader is not None
runtime = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runtime
SPEC.loader.exec_module(runtime)
get_runtime_paths = runtime.get_runtime_paths


def test_reviewer_app_home_isolated_from_existing_user_data(monkeypatch, tmp_path):
    monkeypatch.delenv("MARA_DESKTOP_DATA_DIR", raising=False)
    monkeypatch.setenv("MARA_APP_HOME", str(tmp_path / "reviewer"))

    paths = get_runtime_paths()

    assert paths.config_dir == tmp_path / "reviewer" / "config"
    assert paths.data_dir == tmp_path / "reviewer" / "data"
    assert paths.cache_dir == tmp_path / "reviewer" / "cache"
    assert paths.env_path == paths.config_dir / ".env"
    assert paths.flowsettings_path == paths.config_dir / "flowsettings.py"


def test_desktop_keeps_precedence_over_optional_app_home(monkeypatch, tmp_path):
    monkeypatch.setenv("MARA_APP_HOME", str(tmp_path / "reviewer"))
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(tmp_path / "desktop"))

    assert get_runtime_paths().data_dir == tmp_path / "desktop" / "state" / "runtime"


def test_unset_app_home_preserves_platform_defaults(monkeypatch):
    monkeypatch.delenv("MARA_APP_HOME", raising=False)
    monkeypatch.delenv("MARA_DESKTOP_DATA_DIR", raising=False)
    from platformdirs import PlatformDirs

    expected = PlatformDirs(appname="Kotaemon", appauthor="Cinnamon")
    assert get_runtime_paths().data_dir == Path(expected.user_data_dir).resolve()
