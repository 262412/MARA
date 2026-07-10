from __future__ import annotations

import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest
import tomli


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


def test_initialized_password_container_reprovisions_admin_from_rotated_secret(
    monkeypatch,
):
    from scripts import container_entrypoint

    calls = []
    app_init = SimpleNamespace(
        read_admin_password_file=lambda: "rotated-secret",
        provision_password_admin=lambda **kwargs: calls.append(kwargs),
    )
    monkeypatch.setattr(container_entrypoint, "_runtime_initialized", lambda: True)
    monkeypatch.setitem(__import__("sys").modules, "kotaemon.app_init", app_init)
    monkeypatch.setenv("MARA_ADMIN_USER", "operator")

    container_entrypoint._initialize_runtime("password")

    assert calls == [
        {"username": "operator", "password": "rotated-secret", "force": True}
    ]


def test_container_does_not_force_incompatible_legacy_provider_dependencies():
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "graphrag" not in dockerfile.lower()
    assert "pdfservices-sdk" not in dockerfile.lower()


def test_prepare_nltk_cache_uses_wheel_bundled_data_without_downloading(tmp_path):
    from scripts.prepare_container_nltk import prepare_nltk_cache

    cache = tmp_path / "nltk_cache"
    stopwords = cache / "corpora/stopwords/english"
    stopwords.parent.mkdir(parents=True)
    stopwords.write_text("a\nthe\n", encoding="utf-8")

    prepared = prepare_nltk_cache(cache)

    assert prepared == cache
    assert (cache / "corpora/stopwords/english").is_file()
    assert (cache / "tokenizers/punkt").is_dir()


def test_container_lock_scopes_cpu_torch_without_changing_linux_gpu_runtime():
    repo_root = Path(__file__).resolve().parents[1]
    project = tomli.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomli.loads((repo_root / "uv.lock").read_text(encoding="utf-8"))

    expected_constraints = {
        "mcp==1.12.4",
        "pyarrow==21.0.0",
        "pydantic-settings==2.13.1",
        "pywin32==311; sys_platform == 'win32'",
        "rich==14.1.0",
        "typer==0.19.2",
    }
    assert set(project["tool"]["uv"]["constraint-dependencies"]) == (
        expected_constraints
    )
    assert set(project["tool"]["uv"]["build-constraint-dependencies"]) == {
        "setuptools==80.9.0",
        "setuptools-git-versioning==2.1.0",
        "wheel==0.45.1",
    }
    assert project["tool"]["uv"]["required-version"] == "==0.11.19"
    extras = project["project"]["optional-dependencies"]
    assert extras["container-lite"] == ["mara-research-cli", "torch==2.8.0"]
    assert extras["container-full"] == ["mara-research-cli", "torch==2.8.0"]

    packages = lock["package"]
    sources = project["tool"]["uv"]["sources"]["torch"]
    assert sources == [
        {"index": "pytorch-cpu", "extra": "container-lite"},
        {"index": "pytorch-cpu", "extra": "container-full"},
    ]
    names = {package["name"] for package in packages}
    assert "triton" in names
    assert any(name.startswith("nvidia-") for name in names)
    assert any(
        package.get("name") == "torch"
        and package.get("version") == "2.8.0+cpu"
        and package.get("source", {}).get("registry")
        == "https://download.pytorch.org/whl/cpu"
        for package in packages
    )
    assert any(
        package.get("name") == "torch"
        and package.get("version") == "2.8.0"
        and package.get("source", {}).get("registry") == "https://pypi.org/simple"
        for package in packages
    )


def test_llama_cpp_is_optional_and_not_built_for_container_runtime():
    repo_root = Path(__file__).resolve().parents[1]
    kotaemon = tomli.loads(
        (repo_root / "libs/kotaemon/pyproject.toml").read_text(encoding="utf-8")
    )
    extras = kotaemon["project"]["optional-dependencies"]

    assert not any("llama-cpp-python" in item for item in extras["mara-runtime"])
    assert extras["llama-cpp"] == ["llama-cpp-python<0.2.8"]
    assert "llama-cpp" in extras["all"][0]


def test_readme_uses_non_root_compatible_volume_and_secret_permissions():
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(
        encoding="utf-8"
    )

    assert "docker volume create mara-data" in readme
    assert "type=volume,src=mara-data,dst=/var/lib/mara" in readme
    assert 'chmod 0444 "$MARA_SECRET_FILE"' in readme
    assert "${XDG_RUNTIME_DIR:-/tmp}/mara-admin-password" in readme
    assert "-v ./ktem_app_data:/var/lib/mara" not in readme
