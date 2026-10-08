from __future__ import annotations

import ast
import subprocess
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


def test_container_process_check_requests_pid_column(monkeypatch):
    from scripts import smoke_container_runtime

    commands = []

    def fake_run(*command, check=True):
        commands.append(command)
        stdout = "PID COMMAND\n1 /opt/mara/bin/container-entrypoint\n"
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(smoke_container_runtime, "_run", fake_run)

    smoke_container_runtime._check_runtime("container-id", "lite")

    assert ("docker", "top", "container-id", "-eo", "pid,args") in commands


def test_container_does_not_force_incompatible_legacy_provider_dependencies():
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "graphrag" not in dockerfile.lower()
    assert "pdfservices-sdk" not in dockerfile.lower()
    assert "WORKDIR /var/lib/mara" in dockerfile


def test_final_runtime_base_requires_the_bookworm_pcre2_security_package():
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(
        encoding="utf-8"
    )
    runtime = dockerfile.split(" AS runtime-base\n", 1)[1].split(
        "\nFROM runtime-base AS runtime-full", 1
    )[0]

    assert "libpcre2-8-0=10.42-1+deb12u2" in runtime
    assert "apt-get upgrade" not in runtime
    assert "dist-upgrade" not in runtime


def test_pcre2_probe_records_the_actual_image_and_rejects_evidence_reuse(
    monkeypatch, tmp_path
):
    import hashlib
    import json

    from scripts import smoke_container_runtime as smoke

    calls = []

    def run(*command, check=True, timeout=None):
        calls.append((command, timeout))
        output = '{"checks": {"grep_P": "passed"}}\n'
        if command[1] == "image":
            output = "sha256:owned-image\n"
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(smoke, "_run", run)
    compile(smoke.PCRE2_PROBE, "pcre2-probe", "exec")
    smoke._check_pcre2("owned-container", "owned-tag", "lite", tmp_path)
    record = json.loads((tmp_path / "lite.pcre2.json").read_text())

    assert record["image_id"] == "sha256:owned-image"
    assert (
        record["probe_sha256"] == hashlib.sha256(smoke.PCRE2_PROBE.encode()).hexdigest()
    )
    assert calls[0][0][:3] == ("docker", "exec", "owned-container")
    assert calls[0][1] == 30
    with pytest.raises(FileExistsError, match="new evidence directory"):
        smoke._check_pcre2("owned-container", "owned-tag", "lite", tmp_path)
    assert len(calls) == 2


@pytest.mark.parametrize("timeout", [False, True])
def test_pcre2_probe_preserves_failed_output(monkeypatch, tmp_path, timeout):
    from scripts import smoke_container_runtime as smoke

    def run(*command, **_kwargs):
        if timeout:
            raise subprocess.TimeoutExpired(
                command, 30, output=b"partial identity\n", stderr=b"probe diagnostic\n"
            )
        return subprocess.CompletedProcess(
            command, 1, "partial identity\n", "probe diagnostic\n"
        )

    monkeypatch.setattr(smoke, "_run", run)
    error = subprocess.TimeoutExpired if timeout else RuntimeError
    with pytest.raises(error):
        smoke._check_pcre2("owned-container", "owned-tag", "lite", tmp_path)
    assert (tmp_path / "lite.pcre2.stdout").read_text() == "partial identity\n"
    assert (tmp_path / "lite.pcre2.stderr").read_text() == "probe diagnostic\n"
    assert not (tmp_path / "lite.pcre2.json").exists()


@pytest.mark.parametrize(
    "verification,has_slim_config,accepted",
    [
        ("", False, True),
        (
            "missing     /usr/share/doc/libpcre2-8-0/README.Debian\n"
            "missing     /usr/share/doc/libpcre2-8-0/changelog.Debian.gz\n"
            "missing     /usr/share/doc/libpcre2-8-0/changelog.gz\n",
            True,
            True,
        ),
        ("missing /usr/lib/x86_64-linux-gnu/libpcre2-8.so.0.11.2", True, False),
        ("missing /usr/share/doc/libpcre2-8-0/copyright", True, False),
        ("??5?????? /usr/share/doc/libpcre2-8-0/changelog.gz", True, False),
        ("missing /usr/share/doc/libpcre2-8-0/changelog.gz", False, False),
    ],
)
def test_pcre2_verification_allows_only_fixed_slim_doc_exclusions(
    verification, has_slim_config, accepted
):
    from scripts.smoke_container_runtime import PCRE2_PROBE

    # Execute the same validation function sent to the bounded Linux probe.
    function = next(
        node
        for node in ast.parse(PCRE2_PROBE).body
        if isinstance(node, ast.FunctionDef)
        and node.name == "validate_dpkg_verification"
    )
    namespace: dict = {}
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), "probe", "exec"),
        namespace,
    )
    validate = namespace["validate_dpkg_verification"]
    config = (
        "path-exclude /usr/share/doc/*\npath-include /usr/share/doc/*/copyright\n"
        if has_slim_config
        else ""
    )
    if accepted:
        validate(verification, config)
    else:
        with pytest.raises(AssertionError):
            validate(verification, config)


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


def _export_locked_runtime(repo_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["uv", "export", "--frozen", "--no-dev", "--no-hashes", *arguments],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


@pytest.mark.parametrize("project_path", ("pyproject.toml", "docker/pyproject.toml"))
def test_runtime_dependency_constraints(project_path):
    repo_root = Path(__file__).resolve().parents[1]
    project = tomli.loads((repo_root / project_path).read_text(encoding="utf-8"))

    expected_constraints = {
        "aiohttp>=3.14.3",
        "anyio==4.14.2",
        "cryptography>=50.0.0",
        "filelock==3.32.7",
        "fsspec==2026.6.0",
        "h2>=4.4.1",
        "httpx2>=2.12.0",
        "mcp==1.28.1",
        "oauthlib==4.0.0",
        "onnx>=1.22.0,<1.23; python_version < '3.13'",
        "pyarrow==23.0.1",
        "pydantic-settings==2.14.2",
        "pywin32==311; sys_platform == 'win32'",
        "rich==14.1.0",
        "sentence-transformers==6.0.0",
        "setuptools==83.0.0",
        "soupsieve==2.9",
        "torch==2.13.0",
        "transformers==5.18.0",
        "typer==0.19.2",
        "urllib3==2.8.0",
        "virtualenv==21.7.13",
    }
    if project_path.startswith("docker/"):
        expected_constraints.remove("pywin32==311; sys_platform == 'win32'")
    assert set(project["tool"]["uv"]["constraint-dependencies"]) == expected_constraints
    assert set(project["tool"]["uv"]["build-constraint-dependencies"]) == {
        "setuptools==83.0.0",
        "setuptools-git-versioning==2.1.0",
        "wheel==0.46.2",
    }
    assert project["tool"]["uv"]["required-version"] == "==0.11.19"


def test_container_lock_scopes_cpu_torch_without_changing_linux_gpu_runtime():
    repo_root = Path(__file__).resolve().parents[1]
    project = tomli.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomli.loads((repo_root / "uv.lock").read_text(encoding="utf-8"))
    container_project = tomli.loads(
        (repo_root / "docker/pyproject.toml").read_text(encoding="utf-8")
    )
    container_lock = tomli.loads(
        (repo_root / "docker/uv.lock").read_text(encoding="utf-8")
    )
    packages = lock["package"]
    assert "torch" not in project["tool"]["uv"]["sources"]
    assert container_project["tool"]["uv"]["sources"]["torch"] == {
        "index": "pytorch-cpu"
    }
    names = {package["name"] for package in packages}
    assert "triton" in names
    assert any(name.startswith("nvidia-") for name in names)
    assert any(
        package.get("name") == "torch"
        and package.get("version") == "2.13.0+cpu"
        and package.get("source", {}).get("registry")
        == "https://download.pytorch.org/whl/cpu"
        for package in container_lock["package"]
    )
    assert any(
        package.get("name") == "torch"
        and package.get("version") == "2.13.0"
        and package.get("source", {}).get("registry") == "https://pypi.org/simple"
        for package in packages
    )

    for gpu_export in (
        _export_locked_runtime(repo_root),
        _export_locked_runtime(repo_root, "--extra", "mara"),
    ):
        assert "torch==2.13.0\n" in gpu_export
        assert "torch==2.13.0+cpu" not in gpu_export
        assert "cuda-toolkit==13.0.3" in gpu_export
        assert "nvidia-cudnn-cu13" in gpu_export
        assert "triton==3.7.1" in gpu_export

    cpu_export = _export_locked_runtime(repo_root, "--project", "docker")
    assert "torch==2.13.0+cpu" in cpu_export
    assert "cuda-toolkit" not in cpu_export
    assert "nvidia-cudnn-cu13" not in cpu_export
    assert "triton==3.7.1" not in cpu_export


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
    assert 'install -m 0600 /dev/null "$MARA_SECRET_FILE"' in readme
    assert 'chmod 0444 "$MARA_SECRET_FILE"' in readme
    assert "${XDG_RUNTIME_DIR:-/tmp}/mara-secret.XXXXXX" in readme
    assert "read -rsp 'MARA admin password: ' MARA_ADMIN_PASSWORD" in readme
    assert "unset MARA_ADMIN_PASSWORD" in readme
    assert 'trap \'rm -f "$MARA_SECRET_FILE"; rmdir "$MARA_SECRET_DIR"\' EXIT' in readme
    assert "-v ./ktem_app_data:/var/lib/mara" not in readme


def test_documented_secret_file_permissions_are_non_root_readable_and_cleaned(
    tmp_path,
):
    script = r"""set -eu
MARA_SECRET_DIR="$(mktemp -d "$1/mara-secret.XXXXXX")"
MARA_SECRET_FILE="$MARA_SECRET_DIR/admin-password"
trap 'rm -f "$MARA_SECRET_FILE"; rmdir "$MARA_SECRET_DIR"' EXIT
install -m 0600 /dev/null "$MARA_SECRET_FILE"
MARA_ADMIN_PASSWORD='not-in-the-command-line'
printf '%s\n' "$MARA_ADMIN_PASSWORD" >"$MARA_SECRET_FILE"
unset MARA_ADMIN_PASSWORD
chmod 0444 "$MARA_SECRET_FILE"
test "$(stat -c %a "$MARA_SECRET_FILE")" = 444
test "$(cat "$MARA_SECRET_FILE")" = not-in-the-command-line
printf '%s\n' "$MARA_SECRET_DIR" >"$2"
"""
    marker = tmp_path / "secret-dir"

    completed = subprocess.run(
        ["bash", "-c", script, "bash", str(tmp_path), str(marker)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert not Path(marker.read_text(encoding="utf-8").strip()).exists()


@pytest.mark.parametrize(
    ("version", "models", "error"),
    [("0.31.2", [], None), ("0.0.0", [], "version"), ("0.31.2", {}, "model-list")],
)
def test_ollama_probe_checks_release_version_and_model_api(
    monkeypatch, version, models, error
):
    import io
    import json
    import urllib.request

    from scripts import smoke_container_runtime as smoke

    requests = []
    responses = {
        "http://127.0.0.1:11434/api/version": {"version": version},
        "http://127.0.0.1:11434/api/tags": {"models": models},
    }

    def response(url, *, timeout):
        assert timeout == 5
        requests.append(url)
        return io.StringIO(json.dumps(responses[url]))

    def run(*command, check=True, timeout=None):
        if command[1] == "top":
            return subprocess.CompletedProcess(command, 0, "1 ollama serve", "")
        if command[1] == "exec" and command[3] == "/opt/mara/.venv/bin/python":
            exec(compile(command[-1], "ollama-probe", "exec"), {})
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(urllib.request, "urlopen", response)
    monkeypatch.setattr(smoke, "_run", run)
    if error:
        with pytest.raises(RuntimeError, match=error):
            smoke._check_runtime("container-id", "ollama")
    else:
        smoke._check_runtime("container-id", "ollama")
        assert requests == list(responses)
