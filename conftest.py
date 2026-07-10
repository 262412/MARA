from __future__ import annotations

import atexit

import pytest

from pytest_runtime_isolation import start_process_test_runtime


_TEST_RUNTIME = start_process_test_runtime()
atexit.register(_TEST_RUNTIME.close)


@pytest.fixture(scope="session")
def mara_test_runtime_paths():
    return _TEST_RUNTIME.paths


def pytest_sessionfinish(session, exitstatus):
    _TEST_RUNTIME.close()
