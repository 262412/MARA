from __future__ import annotations

import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


@contextmanager
def _status_server(status: int):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(status)
            self.end_headers()

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_healthcheck_accepts_unauthenticated_401():
    from scripts.container_healthcheck import check_health

    with _status_server(401) as url:
        assert check_health(url, timeout=1.0) is True


def test_healthcheck_rejects_service_unavailable_503():
    from scripts.container_healthcheck import check_health

    with _status_server(503) as url:
        assert check_health(url, timeout=1.0) is False


def test_healthcheck_rejects_connection_failure():
    from scripts.container_healthcheck import check_health

    assert check_health("http://127.0.0.1:1/", timeout=0.05) is False


def test_password_container_requires_mounted_regular_secret(tmp_path):
    from scripts.container_entrypoint import ContainerConfigurationError, validate_auth

    missing = tmp_path / "missing"
    with pytest.raises(ContainerConfigurationError, match="mounted password file"):
        validate_auth("password", missing)

    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(ContainerConfigurationError, match="regular file"):
        validate_auth("password", directory)


def test_password_and_sso_container_auth_modes_are_explicit(tmp_path):
    from scripts.container_entrypoint import validate_auth

    secret = tmp_path / "admin-password"
    secret.write_text("not-baked-into-the-image\n", encoding="utf-8")

    validate_auth("password", secret)
    validate_auth("sso", Path("/not-required-for-sso"))

    with pytest.raises(ValueError, match="password or sso"):
        validate_auth("local", secret)


def test_only_ollama_target_starts_ollama():
    from scripts.container_entrypoint import ollama_command

    assert ollama_command("lite") is None
    assert ollama_command("full") is None
    assert ollama_command("ollama") == ["/usr/bin/ollama", "serve"]
