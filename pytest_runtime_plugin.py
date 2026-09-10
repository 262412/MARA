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
    base = config.option.basetemp
    if base is not None and not Path(base).resolve().is_relative_to(
        _TEST_RUNTIME.paths.root
    ):
        raise pytest.UsageError("pytest basetemp must stay inside the test runtime")
    config.option.basetemp = str(base or _TEST_RUNTIME.paths.root / "pytest")


@pytest.fixture(scope="session")
def mara_test_runtime_paths():
    return _TEST_RUNTIME.paths


def pytest_unconfigure(config):
    _close_test_runtime()
