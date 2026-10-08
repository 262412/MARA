import io
import json
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


@pytest.mark.parametrize("url", [None, "https://user-database.invalid"])
def test_snapshot_requires_an_explicit_owned_service(monkeypatch, tmp_path, url):
    from scripts.prepare_qdrant_test_service import save_snapshot

    monkeypatch.delenv("MARA_TEST_QDRANT_URL", raising=False)
    monkeypatch.setenv("MARA_QDRANT_URL", "https://user-database.invalid")
    if url is not None:
        monkeypatch.setenv("MARA_TEST_QDRANT_URL", url)
    with pytest.raises((KeyError, ValueError)):
        save_snapshot(tmp_path / "vectors.snapshot")
    assert not list(tmp_path.iterdir())


def test_snapshot_never_overwrites_an_existing_artifact(monkeypatch, tmp_path):
    from scripts import prepare_qdrant_test_service as service

    monkeypatch.setenv("MARA_TEST_QDRANT_URL", "http://127.0.0.1:6333")
    output = tmp_path / "vectors.snapshot"
    output.write_bytes(b"existing artifact")

    def unexpected_request(*args, **kwargs):
        pytest.fail("An existing artifact must be rejected before creating a snapshot")

    monkeypatch.setattr(service.urllib.request, "urlopen", unexpected_request)
    with pytest.raises(FileExistsError):
        service.save_snapshot(output)
    assert output.read_bytes() == b"existing artifact"


def test_snapshot_exports_the_owned_service_response(monkeypatch, tmp_path):
    from scripts import prepare_qdrant_test_service as service

    monkeypatch.setenv("MARA_TEST_QDRANT_URL", "http://127.0.0.1:6333/")
    requests = []
    responses = iter(
        [json.dumps({"result": {"name": "test.snapshot"}}).encode(), b"snapshot data"]
    )

    def request(request, **kwargs):
        requests.append(request)
        return io.BytesIO(next(responses))

    monkeypatch.setattr(service.urllib.request, "urlopen", request)
    output = tmp_path / "vectors.snapshot"
    service.save_snapshot(output)
    assert output.read_bytes() == b"snapshot data"
    assert [(item.get_method(), item.full_url) for item in requests] == [
        ("POST", "http://127.0.0.1:6333/snapshots?wait=true"),
        ("GET", "http://127.0.0.1:6333/snapshots/test.snapshot"),
    ]
    assert all(item.get_header("Api-key") == service.TEST_KEY for item in requests)


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
