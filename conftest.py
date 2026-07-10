from __future__ import annotations

import atexit
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pytest_runtime_isolation import start_process_test_runtime


_TEST_RUNTIME = start_process_test_runtime()
atexit.register(_TEST_RUNTIME.close)


@pytest.fixture(scope="session")
def mara_test_runtime_paths():
    return _TEST_RUNTIME.paths


def pytest_sessionfinish(session, exitstatus):
    _TEST_RUNTIME.close()
