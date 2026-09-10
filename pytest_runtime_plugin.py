"""One isolated runtime for repository and package-level pytest entrypoints."""

from __future__ import annotations

import atexit
import sys
import tempfile
from pathlib import Path
from weakref import WeakSet

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine

from pytest_runtime_isolation import start_process_test_runtime

_ORIGINAL_TEMP_DIR = tempfile.tempdir
_ORIGINAL_BYTECODE_FLAG = sys.dont_write_bytecode
_TEST_RUNTIME = start_process_test_runtime()
tempfile.tempdir = str(_TEST_RUNTIME.paths.root / "tmp")
sys.dont_write_bytecode = True
_SESSION_ENGINES: WeakSet[Engine] = WeakSet()


def _track_session_engine(connection: Connection) -> None:
    engine = connection.engine
    database = engine.url.database
    if database and Path(database).resolve().is_relative_to(_TEST_RUNTIME.paths.root):
        _SESSION_ENGINES.add(engine)


event.listen(Engine, "engine_connect", _track_session_engine)


def _close_test_runtime():
    try:
        if not _TEST_RUNTIME.closed:
            event.remove(Engine, "engine_connect", _track_session_engine)
            for engine in _SESSION_ENGINES:
                engine.dispose()
        _TEST_RUNTIME.close()
    finally:
        tempfile.tempdir = _ORIGINAL_TEMP_DIR
        sys.dont_write_bytecode = _ORIGINAL_BYTECODE_FLAG


atexit.register(_close_test_runtime)


def register_plugin(config):
    if not config.pluginmanager.hasplugin(__name__):
        config.pluginmanager.register(sys.modules[__name__], __name__)


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    root = _TEST_RUNTIME.require_owned_root()
    base = Path(config.option.basetemp or root / "pytest").expanduser().absolute()
    if (
        base != base.resolve()
        or base == root
        or not base.is_relative_to(root)
        or (base.exists() and not base.is_dir())
    ):
        raise pytest.UsageError(
            "pytest basetemp must be a dedicated owned subdirectory"
        )
    state_paths = (
        root / "config",
        root / "tmp",
        _TEST_RUNTIME.paths.app_data_dir,
        _TEST_RUNTIME.paths.cache_dir,
        _TEST_RUNTIME.paths.output_dir,
    )
    if any(
        base.is_relative_to(path) or path.is_relative_to(base) for path in state_paths
    ):
        raise pytest.UsageError("pytest basetemp cannot overlap runtime state")
    config.option.basetemp = str(base)


@pytest.fixture(scope="session")
def mara_test_runtime_paths():
    return _TEST_RUNTIME.paths


def pytest_unconfigure(config):
    _close_test_runtime()
