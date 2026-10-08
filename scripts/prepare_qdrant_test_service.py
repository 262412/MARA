"""Explicitly start a pinned, loopback-only Qdrant service for isolated CI tests."""

import argparse
import hashlib
import json
import os
import shutil
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
from urllib.parse import quote, urlsplit

VERSION = "1.19.2"
ASSETS = {
    "win32": (
        "qdrant-x86_64-pc-windows-msvc.zip",
        "7d86596f16c6e85d45a50312f5e16ccb51e059b62e3d7308110cb65b4c799a4d",
    ),
    "linux": (
        "qdrant-x86_64-unknown-linux-musl.tar.gz",
        "50b253243309ed0ae50a19f678f0d0adcc4f0b567b3bd2c5c0c7e02fa8404bb6",
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


def start_service(root, executable, restore_snapshot=None):
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
    command = [str(executable), "--config-path", str(configuration)]
    if restore_snapshot is not None:
        command.extend(["--storage-snapshot", str(restore_snapshot.resolve())])
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW
    with (root / "server.log").open("xb") as log:
        process = subprocess.Popen(
            command,
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
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


def save_snapshot(output):
    url = os.environ["MARA_TEST_QDRANT_URL"].rstrip("/")
    if urlsplit(url).hostname != "127.0.0.1":
        raise ValueError("Snapshot export requires the owned loopback test service")
    headers = {"api-key": TEST_KEY}
    with output.open("xb") as destination:
        request = urllib.request.Request(
            url + "/snapshots?wait=true", headers=headers, method="POST"
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            snapshot = json.load(response)["result"]
        request = urllib.request.Request(
            url + "/snapshots/" + quote(snapshot["name"], safe=""), headers=headers
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            shutil.copyfileobj(response, destination)
    print(f"Saved test vector snapshot: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--restore-snapshot", type=Path)
    parser.add_argument("--snapshot-output", type=Path)
    args = parser.parse_args()
    if args.snapshot_output:
        save_snapshot(args.snapshot_output)
        return
    if args.root:
        root = args.root.resolve()
        root.mkdir(parents=True, exist_ok=False)
    else:
        root = Path(tempfile.mkdtemp(prefix="qd-", dir=os.environ.get("RUNNER_TEMP")))
    url = start_service(root, prepare_binary(root, args.archive), args.restore_snapshot)
    if destination := os.environ.get("GITHUB_ENV"):
        with Path(destination).open("a", encoding="utf-8") as stream:
            for prefix in ("MARA_QDRANT", "MARA_TEST_QDRANT"):
                stream.write(f"{prefix}_URL={url}\n{prefix}_API_KEY={TEST_KEY}\n")
    print(json.dumps({"url": url, "root": str(root), "version": VERSION}))


if __name__ == "__main__":
    main()
