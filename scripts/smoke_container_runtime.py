from __future__ import annotations

import argparse
import subprocess
import time
import uuid
from pathlib import Path


def _run(*command: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return completed


def _inspect(image: str) -> None:
    user = _run(
        "docker", "image", "inspect", image, "--format", "{{.Config.User}}"
    ).stdout.strip()
    if user != "10001:10001":
        raise RuntimeError(f"Container image user is {user!r}, expected 10001:10001")
    healthcheck = _run(
        "docker",
        "image",
        "inspect",
        image,
        "--format",
        "{{json .Config.Healthcheck}}",
    ).stdout.strip()
    if healthcheck in {"", "null", "<no value>"}:
        raise RuntimeError("Container image has no healthcheck")


def _wait_for_health(container: str, timeout: float = 180.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = _run(
            "docker",
            "inspect",
            container,
            "--format",
            "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}",
        ).stdout.strip()
        if state == "running healthy":
            return
        if not state.startswith("running"):
            break
        time.sleep(2)
    logs = _run("docker", "logs", container, check=False)
    detail = (logs.stdout + logs.stderr).strip()
    raise RuntimeError(f"Container did not become healthy: {detail}")


def _check_runtime(container: str, target: str) -> None:
    _run(
        "docker",
        "exec",
        container,
        "sh",
        "-ec",
        (
            'test -w "$KH_APP_DATA_DIR"; '
            'probe="$KH_APP_DATA_DIR/.runtime-smoke"; '
            'touch "$probe"; rm "$probe"; test ! -w /opt/mara'
        ),
    )
    processes = _run("docker", "top", container, "-eo", "args").stdout
    has_ollama = "ollama serve" in processes
    if has_ollama != (target == "ollama"):
        raise RuntimeError(
            f"Unexpected Ollama process state for {target}: running={has_ollama}"
        )
    if target == "ollama":
        _run(
            "docker",
            "exec",
            container,
            "/opt/mara/.venv/bin/python",
            "-c",
            (
                "import socket; s=socket.create_connection("
                "('127.0.0.1', 11434), timeout=5); s.close()"
            ),
        )


def smoke(image: str, target: str, secret_file: Path) -> None:
    if not secret_file.is_file():
        raise RuntimeError(f"Password secret is not a regular file: {secret_file}")
    _inspect(image)
    suffix = uuid.uuid4().hex[:12]
    container = f"mara-smoke-{target}-{suffix}"
    volume = f"mara-smoke-data-{target}-{suffix}"
    _run("docker", "volume", "create", volume)
    try:
        _run(
            "docker",
            "run",
            "--detach",
            "--name",
            container,
            "--mount",
            (
                f"type=bind,src={secret_file.resolve()},"
                "dst=/run/secrets/mara_admin_password,readonly"
            ),
            "--mount",
            f"type=volume,src={volume},dst=/var/lib/mara",
            image,
        )
        _wait_for_health(container)
        _check_runtime(container, target)
    finally:
        _run("docker", "rm", "--force", container, check=False)
        _run("docker", "volume", "rm", volume, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke a built MARA container target.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--target", choices=("lite", "full", "ollama"), required=True)
    parser.add_argument("--secret-file", type=Path, required=True)
    args = parser.parse_args()
    smoke(args.image, args.target, args.secret_file)
    print(f"Container runtime smoke passed: {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
