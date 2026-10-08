"""Explicitly start a pinned, loopback-only Qdrant service for isolated CI tests."""

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

VERSION = "1.19.2"
ASSETS = {
    "win32": (
        "qdrant-x86_64-pc-windows-msvc.zip",
        "7d86596f16c6e85d45a50312f5e16ccb51e059b62e3d7308110cb65b4c799a4d",
    ),
    "linux": (
        "qdrant-x86_64-unknown-linux-gnu.tar.gz",
        "34a788a09a4cb278b5c6d2af96d9a6db30c8c7e88ae3550455f7a4d425bb8d4b",
    ),
}
TEST_KEY = "mara-owned-synthetic-test"


def prepare_binary(root, archive=None):
    asset, digest = ASSETS[sys.platform]
    if archive is None:
        url = f"https://github.com/qdrant/qdrant/releases/download/v{VERSION}/{asset}"
        archive = root / asset
        with urllib.request.urlopen(url, timeout=120) as response:
            archive.write_bytes(response.read())
    data = archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("Qdrant release archive SHA-256 mismatch")
    executable = root / ("qdrant.exe" if sys.platform == "win32" else "qdrant")
    if sys.platform == "win32":
        with zipfile.ZipFile(archive) as bundle:
            payload = bundle.read("qdrant.exe")
    else:
        with tarfile.open(archive) as bundle:
            members = [
                item
                for item in bundle.getmembers()
                if Path(item.name).name == "qdrant" and item.isfile()
            ]
            if len(members) != 1:
                raise ValueError("Qdrant archive must contain one regular executable")
            stream = bundle.extractfile(members[0])
            if stream is None:
                raise ValueError("Cannot read Qdrant executable")
            with stream:
                payload = stream.read()
    executable.write_bytes(payload)
    executable.chmod(0o700)
    return executable


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_ready(process, url):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Qdrant exited before readiness; inspect server.log")
        try:
            request = urllib.request.Request(url + "/", headers={"api-key": TEST_KEY})
            with urllib.request.urlopen(request, timeout=2) as response:
                if json.load(response)["version"] == VERSION:
                    break
        except (OSError, ValueError):
            time.sleep(0.2)
    else:
        raise TimeoutError("Qdrant did not become ready")
    try:
        urllib.request.urlopen(url + "/collections", timeout=2).close()
    except urllib.error.HTTPError as error:
        if error.code == 401:
            return
        raise
    raise RuntimeError("The test Qdrant service did not enforce API authentication")


def start_service(root, executable):
    http_port, grpc_port = free_port(), free_port()
    while http_port == grpc_port:
        grpc_port = free_port()
    config = {
        "log_level": "WARN",
        "telemetry_disabled": True,
        "service": {
            "host": "127.0.0.1",
            "http_port": http_port,
            "grpc_port": grpc_port,
            "api_key": TEST_KEY,
            "max_workers": 2,
        },
        "storage": {
            "storage_path": str(root / "storage"),
            "snapshots_path": str(root / "snapshots"),
            "performance": {"max_search_threads": 2},
            "wal": {"wal_capacity_mb": 1},
            "optimizers": {"default_segment_number": 1},
        },
    }
    configuration = root / "config.yaml"
    configuration.write_text(json.dumps(config), encoding="utf-8")
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("QDRANT__")
    }
    env.update(
        QDRANT__SERVICE__HOST="127.0.0.1",
        QDRANT__SERVICE__HTTP_PORT=str(http_port),
        QDRANT__SERVICE__GRPC_PORT=str(grpc_port),
        QDRANT__SERVICE__API_KEY=TEST_KEY,
        QDRANT__SERVICE__MAX_WORKERS="2",
        QDRANT__TELEMETRY_DISABLED="true",
    )
    with (root / "server.log").open("xb") as log:
        process = subprocess.Popen(
            [str(executable), "--config-path", str(configuration)],
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    url = f"http://127.0.0.1:{http_port}"
    try:
        wait_ready(process, url)
    except BaseException:
        process.terminate()
        process.wait(timeout=10)
        raise
    (root / "process.json").write_text(
        json.dumps({"pid": process.pid, "exe": str(executable), "url": url}),
        encoding="utf-8",
    )
    return url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    if args.root:
        root = args.root.resolve()
        root.mkdir(parents=True, exist_ok=False)
    else:
        root = Path(tempfile.mkdtemp(prefix="qd-", dir=os.environ.get("RUNNER_TEMP")))
    url = start_service(root, prepare_binary(root, args.archive))
    if destination := os.environ.get("GITHUB_ENV"):
        with Path(destination).open("a", encoding="utf-8") as stream:
            for prefix in ("MARA_QDRANT", "MARA_TEST_QDRANT"):
                stream.write(f"{prefix}_URL={url}\n{prefix}_API_KEY={TEST_KEY}\n")
    print(json.dumps({"url": url, "root": str(root), "version": VERSION}))


if __name__ == "__main__":
    main()
