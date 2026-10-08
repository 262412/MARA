"""Verify the installed backport, monitor base advisories, and run upstream tests."""

import argparse
import hashlib
import importlib.metadata
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

VENDOR = Path(__file__).resolve().parents[1] / "vendor/nltk"
TAGGER_URL = (
    "https://raw.githubusercontent.com/nltk/nltk_data/"
    "550b6625bcef1f2abff2ff770a5a0d272c9c6b2a/packages/taggers/"
    "averaged_perceptron_tagger_eng.zip"
)
TAGGER_SHA256 = "6025f530624335c67d6547d44757b357b4e79bae030a0383e9887a92c1718f0b"
TESTS = (
    "test_model_artifact_pathsec.py",
    "test_maxent_save_security.py",
    "test_pathsec_sweep_transitionparser.py",
)


def verify_installed():
    manifest = json.loads((VENDOR / "backport.json").read_text(encoding="utf-8"))
    base = json.loads((VENDOR / "base-files.json").read_text(encoding="utf-8"))
    distribution = importlib.metadata.distribution("nltk")
    if distribution.version != manifest["version"]:
        raise ValueError("NLTK is not the locked MARA security backport")
    provenance = distribution.read_text("MARA-BACKPORT.json")
    if provenance is None or json.loads(provenance) != manifest:
        raise ValueError(
            "Installed NLTK provenance does not match the reviewed backport"
        )
    expected = {
        name: digest
        for name, digest in {**base, **manifest["files"]}.items()
        if name.startswith("nltk/")
    }
    for name, digest in expected.items():
        if (
            hashlib.sha256(
                Path(distribution.locate_file(name)).read_bytes()
            ).hexdigest()
            != digest
        ):
            raise ValueError(f"Installed NLTK source hash mismatch: {name}")
    package = Path(distribution.locate_file("nltk"))
    actual = {
        "nltk/" + path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    if actual != set(expected):
        raise ValueError("Installed NLTK contains unexpected or missing package files")
    print(
        f"Verified NLTK {distribution.version}: {len(expected)} package files",
        flush=True,
    )
    return distribution


def check_advisories(report):
    if not isinstance(report, dict) or set(report) - {"vulns"}:
        raise ValueError("Invalid OSV response")
    vulnerabilities = report.get("vulns", [])
    if not isinstance(vulnerabilities, list):
        raise ValueError("Invalid OSV vulnerability list")
    fixed = {"GHSA-8mgp-746c-j5xp", "CVE-2026-81726", "PYSEC-2026-3740"}
    unhandled = []
    for vulnerability in vulnerabilities:
        if not isinstance(vulnerability, dict) or not isinstance(
            vulnerability.get("id"), str
        ):
            raise ValueError("Invalid OSV vulnerability record")
        aliases = vulnerability.get("aliases", [])
        if not isinstance(aliases, list) or not all(
            isinstance(value, str) for value in aliases
        ):
            raise ValueError("Invalid OSV vulnerability aliases")
        identifiers = {vulnerability["id"], *vulnerability.get("aliases", [])}
        if not identifiers & fixed:
            unhandled.append(vulnerability["id"])
    if unhandled:
        raise ValueError(
            "New NLTK base advisories require review: " + ", ".join(unhandled)
        )


def check_upstream_advisories():
    request = urllib.request.Request(
        "https://api.osv.dev/v1/query",
        data=json.dumps(
            {"package": {"name": "nltk", "ecosystem": "PyPI"}, "version": "3.10.3"}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        report = json.load(response)
    check_advisories(report)
    print(
        "NLTK base advisory check passed; the known finding has verified source remediation"
    )


def _test_resources(root, tagger_archive):
    core = importlib.metadata.distribution("llama-index-core")
    cache = root / "cache/nltk"
    shutil.copytree(core.locate_file("llama_index/core/_static/nltk_cache"), cache)
    (cache / "tokenizers/punkt").mkdir(parents=True, exist_ok=True)
    if tagger_archive:
        data = tagger_archive.read_bytes()
    else:
        with urllib.request.urlopen(TAGGER_URL, timeout=30) as response:
            data = response.read(2 * 1024 * 1024)
    if hashlib.sha256(data).hexdigest() != TAGGER_SHA256:
        raise ValueError("Upstream JSON tagger fixture hash mismatch")
    prefix = "averaged_perceptron_tagger_eng"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for suffix in ("weights", "tagdict", "classes"):
            name = f"{prefix}/{prefix}.{suffix}.json"
            path = cache / "taggers" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(name))
    return cache


def _run_upstream_tests(distribution, tagger_archive):
    parent = Path(os.environ.get("MARA_PYTEST_RUNTIME_PARENT", tempfile.gettempdir()))
    parent.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="nltk-security-", dir=parent)).resolve()
    for name in ("home", "tmp", "workspace"):
        (root / name).mkdir()
    cache = _test_resources(root, tagger_archive)
    env = dict(os.environ)
    env.update(
        HOME=str(root / "home"),
        USERPROFILE=str(root / "home"),
        APPDATA=str(root / "home"),
        LOCALAPPDATA=str(root / "home"),
        TEMP=str(root / "tmp"),
        TMP=str(root / "tmp"),
        TMPDIR=str(root / "tmp"),
        NLTK_DATA=str(cache),
        XDG_CACHE_HOME=str(root / "cache"),
        MPLCONFIGDIR=str(root / "cache/matplotlib"),
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        NLTK_SECURITY_ROOT=str(root),
    )
    tests = [str(distribution.locate_file("nltk/test/unit/" + name)) for name in TESTS]
    command = [
        sys.executable,
        "-I",
        "-B",
        str(Path(__file__).resolve()),
        "--child",
        *tests,
        "-q",
        "-rs",
        "-p",
        "pytest_mock",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        "--confcutdir=" + str(distribution.locate_file("nltk/test")),
        "--basetemp=" + str(root / "pytest"),
        "--junitxml=" + str(root / "results.xml"),
    ]
    print(f"NLTK security regression artifacts: {root}", flush=True)
    return subprocess.run(
        command, env=env, cwd=root / "workspace", check=False
    ).returncode


def _child_tests(args):
    root = Path(os.environ["NLTK_SECURITY_ROOT"]).resolve()

    def protect_cleanup(event, values):
        if event == "shutil.rmtree":
            target = Path(values[0]).resolve()
            if target == root or not target.is_relative_to(root):
                raise RuntimeError("NLTK test cleanup escaped its owned directory")

    def offline(*args, **kwargs):
        raise RuntimeError(
            "Network access and corpus downloads are disabled in NLTK tests"
        )

    sys.addaudithook(protect_cleanup)
    setattr(socket.socket, "connect", offline)
    setattr(socket.socket, "connect_ex", offline)
    import nltk
    import pytest

    nltk.download = offline
    return pytest.main(args)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--child":
        return _child_tests(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--advisories", action="store_true")
    parser.add_argument("--tests", action="store_true")
    parser.add_argument("--tagger-archive", type=Path)
    args = parser.parse_args(argv)
    distribution = verify_installed()
    if args.advisories:
        check_upstream_advisories()
    return _run_upstream_tests(distribution, args.tagger_archive) if args.tests else 0


if __name__ == "__main__":
    raise SystemExit(main())
