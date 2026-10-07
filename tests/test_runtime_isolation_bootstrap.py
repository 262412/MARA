from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from pytest_runtime_isolation import activate_test_runtime, restore_environment

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bootstrap(monkeypatch):
    """Read the bootstrap without executing the business package's __init__."""
    name = "_isolated_bootstrap_probe"
    spec = importlib.util.spec_from_file_location(
        name, REPO_ROOT / "libs/ktem/ktem/runtime_bootstrap.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("inherited_desktop", [False, True])
def test_activation_contains_resolved_paths_and_restores_overrides(
    bootstrap, monkeypatch, tmp_path, inherited_desktop
):
    outside = tmp_path / "user-candidate"
    environment = {"THEFLOW_SETTINGS_MODULE": str(outside / "flowsettings.py")}
    if inherited_desktop:
        environment["MARA_DESKTOP_DATA_DIR"] = str(outside)
        environment["MARA_DESKTOP_CHAT_MODEL"] = "inherited-model"
    original = dict(environment)
    monkeypatch.setattr(os, "environ", environment)
    monkeypatch.setattr(
        bootstrap,
        "PlatformDirs",
        lambda **_: SimpleNamespace(
            user_config_dir=str(outside / "config"),
            user_data_dir=str(outside / "data"),
            user_cache_dir=str(outside / "cache"),
        ),
    )
    snapshot, paths = activate_test_runtime(environment, tmp_path / "session")

    try:
        effective = bootstrap.get_runtime_paths()
        for path in (
            effective.config_dir,
            effective.data_dir,
            effective.cache_dir,
            effective.flowsettings_path,
            effective.env_path,
        ):
            assert path.is_relative_to(paths.root)
        assert not any(key.startswith("MARA_DESKTOP_") for key in environment)
        assert not outside.exists()
    finally:
        restore_environment(environment, snapshot)

    assert environment == original


def test_explicit_nltk_cache_never_prepares_the_installed_package(
    bootstrap, monkeypatch, tmp_path
):
    installed = tmp_path / "installed"
    bundled = installed / "llama_index/core/_static/nltk_cache"
    bundled.mkdir(parents=True)
    isolated = tmp_path / "session/nltk"
    monkeypatch.setenv("NLTK_DATA", str(isolated))
    monkeypatch.setattr(bootstrap.sys, "path", [str(installed)])

    bootstrap.ensure_llama_index_nltk_cache()

    assert not (bundled / "tokenizers").exists()
    assert (isolated / "tokenizers/punkt").is_dir()


def test_external_runtime_override_is_rejected_before_any_directory_write(
    bootstrap, monkeypatch, tmp_path
):
    environment: dict[str, str] = {}
    monkeypatch.setattr(os, "environ", environment)
    activate_test_runtime(environment, tmp_path / "session")
    environment["KH_APP_DATA_DIR"] = str(tmp_path / "outside")

    def unexpected_write(*_args, **_kwargs):
        pytest.fail("bootstrap attempted a write before validating isolation")

    monkeypatch.setattr(Path, "mkdir", unexpected_write)
    with pytest.raises(RuntimeError, match="outside.*test runtime"):
        bootstrap.load_packaged_runtime_env()


def test_default_platform_paths_remain_unchanged_without_test_activation(
    bootstrap, monkeypatch, tmp_path
):
    monkeypatch.setattr(os, "environ", {})
    defaults = SimpleNamespace(
        user_config_dir=str(tmp_path / "config"),
        user_data_dir=str(tmp_path / "data"),
        user_cache_dir=str(tmp_path / "cache"),
    )
    monkeypatch.setattr(bootstrap, "PlatformDirs", lambda **_: defaults)

    paths = bootstrap.get_runtime_paths()

    assert paths.config_dir == Path(defaults.user_config_dir)
    assert paths.data_dir == Path(defaults.user_data_dir)
    assert paths.cache_dir == Path(defaults.user_cache_dir)


def test_close_refuses_a_runtime_it_did_not_create(tmp_path):
    from pytest_runtime_isolation import ActiveTestRuntime, TestRuntimePaths

    outside = tmp_path / "not-session-owned"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    environment = {"MARA_RUNTIME_DIR": "temporary"}
    runtime = ActiveTestRuntime(
        environment=environment,
        snapshot={"MARA_RUNTIME_DIR": "original"},
        paths=TestRuntimePaths.from_root(outside),
    )

    with pytest.raises(RuntimeError, match="not owned"):
        runtime.close()

    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert environment == {"MARA_RUNTIME_DIR": "original"}


def test_owned_cleanup_restores_environment_and_preserves_siblings(tmp_path):
    from pytest_runtime_isolation import ActiveTestRuntime

    sibling = tmp_path / "keep.txt"
    sibling.write_text("keep", encoding="utf-8")
    environment = {"MARA_PYTEST_RUNTIME_PARENT": str(tmp_path)}
    original = dict(environment)
    runtime = ActiveTestRuntime.start(environment)
    root = runtime.paths.root

    runtime.close()
    runtime.close()

    assert not root.exists()
    assert sibling.read_text(encoding="utf-8") == "keep"
    assert environment == original


def test_owned_cleanup_removes_readonly_fixtures_but_preserves_siblings(tmp_path):
    import stat

    from pytest_runtime_isolation import ActiveTestRuntime

    sibling = tmp_path / "keep.txt"
    sibling.write_text("keep", encoding="utf-8")
    sibling.chmod(stat.S_IREAD)
    sibling_mode = sibling.stat().st_mode
    runtime = ActiveTestRuntime.start({"MARA_PYTEST_RUNTIME_PARENT": str(tmp_path)})
    fixture = runtime.paths.root / "readonly-fixture"
    fixture.write_text("owned", encoding="utf-8")
    fixture.chmod(stat.S_IREAD)

    try:
        runtime.close()
        assert not runtime.paths.root.exists()
        assert sibling.read_text(encoding="utf-8") == "keep"
        assert sibling.stat().st_mode == sibling_mode
    finally:
        sibling.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_tampered_owner_marker_blocks_cleanup(tmp_path):
    from pytest_runtime_isolation import OWNER_MARKER, ActiveTestRuntime

    environment = {"MARA_PYTEST_RUNTIME_PARENT": str(tmp_path)}
    original = dict(environment)
    runtime = ActiveTestRuntime.start(environment)
    marker = runtime.paths.root / OWNER_MARKER
    marker.write_text("different-owner", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not owned"):
        runtime.close()

    assert runtime.paths.root.is_dir()
    assert marker.read_text(encoding="utf-8") == "different-owner"
    assert environment == original


def test_runtime_parent_cannot_be_the_python_environment(monkeypatch, tmp_path):
    from pytest_runtime_isolation import create_session_runtime_root

    prefix = tmp_path / "canonical-env"
    monkeypatch.setattr(sys, "prefix", str(prefix))

    with pytest.raises(RuntimeError, match="inside the Python environment"):
        create_session_runtime_root({"MARA_PYTEST_RUNTIME_PARENT": str(prefix / "tmp")})

    assert not prefix.exists()


@pytest.mark.parametrize("module_name", ["ktem", "theflow.settings"])
def test_isolation_rejects_already_initialized_runtime(monkeypatch, module_name):
    from pytest_runtime_isolation import start_process_test_runtime

    monkeypatch.delitem(sys.modules, "ktem", raising=False)
    loaded = SimpleNamespace(settings=SimpleNamespace(_initialized=True))
    monkeypatch.setitem(sys.modules, module_name, loaded)
    with pytest.raises(RuntimeError, match="before importing ktem"):
        start_process_test_runtime()


def test_owned_cleanup_closes_its_sqlite_pool(monkeypatch, tmp_path):
    import sqlite3

    from sqlalchemy import create_engine

    from pytest_runtime_isolation import ActiveTestRuntime

    runtime = ActiveTestRuntime.start({"MARA_PYTEST_RUNTIME_PARENT": str(tmp_path)})
    engine = create_engine(f"sqlite:///{runtime.paths.database_path}")
    with engine.connect() as connection:
        pooled_connection = connection.connection.driver_connection
        assert pooled_connection is not None
        connection.exec_driver_sql("CREATE TABLE canary (id INTEGER)")
    monkeypatch.setitem(sys.modules, "ktem.db.engine", SimpleNamespace(engine=engine))

    try:
        runtime.close()
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            pooled_connection.execute("SELECT 1")
        assert not runtime.paths.root.exists()
    finally:
        engine.dispose()


def test_cleanup_does_not_close_a_different_runtime_database(monkeypatch, tmp_path):
    from sqlalchemy import create_engine

    from pytest_runtime_isolation import ActiveTestRuntime

    outside = tmp_path / "other-runtime.db"
    engine = create_engine(f"sqlite:///{outside}")
    with engine.connect() as connection:
        pooled_connection = connection.connection.driver_connection
        assert pooled_connection is not None
        connection.exec_driver_sql("CREATE TABLE canary (id INTEGER)")
    monkeypatch.setitem(sys.modules, "ktem.db.engine", SimpleNamespace(engine=engine))
    runtime = ActiveTestRuntime.start({"MARA_PYTEST_RUNTIME_PARENT": str(tmp_path)})

    try:
        runtime.close()
        assert pooled_connection.execute("SELECT 1").fetchone() == (1,)
        assert outside.exists()
    finally:
        engine.dispose()


@pytest.mark.parametrize("owned", [True, False])
def test_cleanup_closes_only_session_owned_theflow_caches(monkeypatch, tmp_path, owned):
    import sqlite3

    from diskcache import Cache

    from pytest_runtime_isolation import ActiveTestRuntime

    runtime = ActiveTestRuntime.start({"MARA_PYTEST_RUNTIME_PARENT": str(tmp_path)})
    path = (runtime.paths.root if owned else tmp_path) / "file-cache"
    cache = Cache(str(path))
    connection = cache._con
    registry = {str(path): cache}
    monkeypatch.setitem(
        sys.modules, "theflow.cache.filebased", SimpleNamespace(_local_caches=registry)
    )
    try:
        runtime.close()
        if owned:
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                connection.execute("SELECT 1")
            assert registry == {}
        else:
            assert connection.execute("SELECT 1").fetchone() == (1,)
            assert registry == {str(path): cache}
    finally:
        cache.close()
