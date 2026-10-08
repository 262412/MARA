import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest


def test_runtime_does_not_inherit_live_qdrant_configuration(monkeypatch, tmp_path):
    from pytest_runtime_isolation import (
        TestRuntimePaths,
        activate_test_runtime,
        restore_environment,
    )

    monkeypatch.delenv("MARA_TEST_QDRANT_URL", raising=False)
    monkeypatch.delenv("MARA_TEST_QDRANT_API_KEY", raising=False)
    monkeypatch.setattr(TestRuntimePaths, "create_directories", lambda self: None)
    environment = {
        "MARA_QDRANT_URL": "https://user-database.invalid",
        "MARA_QDRANT_API_KEY": "synthetic-original-value",
        "MARA_QDRANT_NAMESPACE": "live_database",
    }
    original = dict(environment)
    snapshot, _ = activate_test_runtime(environment, tmp_path)
    assert environment["MARA_QDRANT_URL"] == "http://127.0.0.1:1"
    assert environment["MARA_QDRANT_API_KEY"] == ""
    assert environment["MARA_QDRANT_NAMESPACE"] == ""
    restore_environment(environment, snapshot)
    assert environment == original


def test_runtime_uses_only_explicit_loopback_test_service():
    from pytest_runtime_isolation import isolated_vector_service

    values = isolated_vector_service(
        {
            "MARA_TEST_QDRANT_URL": "http://127.0.0.1:6333",
            "MARA_TEST_QDRANT_API_KEY": "synthetic-test-only",
            "MARA_QDRANT_NAMESPACE": "live_database",
        }
    )
    assert values == {
        "MARA_QDRANT_URL": "http://127.0.0.1:6333",
        "MARA_QDRANT_API_KEY": "synthetic-test-only",
        "MARA_QDRANT_NAMESPACE": "",
    }
    with pytest.raises(ValueError, match="loopback"):
        isolated_vector_service(
            {"MARA_TEST_QDRANT_URL": "https://user-database.invalid"}
        )


def test_qdrant_release_hash_mismatch_never_extracts_a_binary(tmp_path):
    from scripts.prepare_qdrant_test_service import prepare_binary

    archive = tmp_path / "untrusted.zip"
    archive.write_bytes(b"modified release")
    with pytest.raises(ValueError, match="SHA-256"):
        prepare_binary(tmp_path, archive)
    assert list(tmp_path.iterdir()) == [archive]


@pytest.mark.parametrize("owned", [False, True])
def test_wheel_network_guard_allows_only_the_owned_service(owned):
    guard = Path(__file__).resolve().parents[1] / "scripts/clean_wheel_network_guard.py"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(5)
        port = listener.getsockname()[1]
        code = """
import runpy, socket, sys
runpy.run_path(sys.argv[1])
owned, port = sys.argv[2] == 'True', int(sys.argv[3])
for method in ('connect', 'connect_ex'):
    for address in [('127.0.0.1', port), ('127.0.0.1', port + 1), ('203.0.113.1', 443)]:
        with socket.socket() as connection:
            connection.settimeout(1)
            try:
                getattr(connection, method)(address)
            except RuntimeError as error:
                assert 'forbidden' in str(error)
                assert not (owned and address == ('127.0.0.1', port))
            else:
                assert owned and address == ('127.0.0.1', port)
"""
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c", code, str(guard), str(owned), str(port)],
            env={
                **os.environ,
                "MARA_TEST_QDRANT_URL": f"http://127.0.0.1:{port}" if owned else "",
            },
            capture_output=True,
            text=True,
            timeout=15,
        )
    assert result.returncode == 0, result.stdout + result.stderr
