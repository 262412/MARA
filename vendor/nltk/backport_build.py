"""Build a source-verified NLTK backport without importing the vulnerable base."""

import base64
import csv
import hashlib
import importlib.metadata
import io
import json
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = "3.10.3.post1+mara.1"
DIST_INFO = f"nltk-{VERSION}.dist-info"
WHEEL_NAME = f"nltk-{VERSION}-py3-none-any.whl"


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _stage_base(destination):
    base = importlib.metadata.distribution("nltk")
    if base.version != "3.10.3":
        raise ValueError("The backport build requires the unmodified NLTK 3.10.3 wheel")
    manifest = json.loads((ROOT / "base-files.json").read_text(encoding="utf-8"))
    for name, expected in manifest.items():
        data = Path(base.locate_file(name)).read_bytes()
        if _sha256(data) != expected:
            raise ValueError(f"NLTK base file hash mismatch: {name}")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return manifest


def _apply_patch(destination, base):
    manifest = json.loads((ROOT / "backport.json").read_text(encoding="utf-8"))
    patch = ROOT / "security.patch"
    if _sha256(patch.read_bytes()) != manifest["patch_sha256"]:
        raise ValueError("NLTK security patch hash mismatch")
    command = ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "apply"]
    subprocess.run([*command, "--check", str(patch)], cwd=destination, check=True)
    subprocess.run([*command, str(patch)], cwd=destination, check=True)
    expected = {**base, **manifest["files"]}
    for name, digest in expected.items():
        if _sha256((destination / name).read_bytes()) != digest:
            raise ValueError(f"NLTK patched file hash mismatch: {name}")
    actual = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file()
    }
    if actual != set(expected):
        raise ValueError("NLTK patch introduced unexpected files")
    return manifest


def _distribution_files(staging, manifest):
    original = staging / "nltk-3.10.3.dist-info"
    renamed = staging / DIST_INFO
    if (
        original.resolve().parent != staging.resolve()
        or renamed.resolve().parent != staging.resolve()
    ):
        raise ValueError("Distribution metadata path escaped the build directory")
    original.rename(renamed)
    metadata = renamed / "METADATA"
    content = metadata.read_text(encoding="utf-8")
    content = content.replace("Version: 3.10.3\n", f"Version: {VERSION}\n", 1)
    content = content.replace(
        "Summary: Natural Language Toolkit",
        "Summary: Natural Language Toolkit (MARA security backport)",
        1,
    )
    metadata.write_text(content, encoding="utf-8", newline="\n")
    (renamed / "MARA-BACKPORT.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8", newline="\n"
    )


def _write_wheel(staging, output):
    files = {
        path.relative_to(staging).as_posix(): path.read_bytes()
        for path in staging.rglob("*")
        if path.is_file() and path.name != "RECORD"
    }
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, data in sorted(files.items()):
        digest = (
            base64.urlsafe_b64encode(hashlib.sha256(data).digest())
            .rstrip(b"=")
            .decode()
        )
        writer.writerow([name, "sha256=" + digest, len(data)])
    writer.writerow([f"{DIST_INFO}/RECORD", "", ""])
    files[f"{DIST_INFO}/RECORD"] = record.getvalue().encode()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as wheel:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 8, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            wheel.writestr(info, data)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    with tempfile.TemporaryDirectory(prefix="mara-nltk-build-") as temporary:
        staging = Path(temporary)
        base = _stage_base(staging)
        manifest = _apply_patch(staging, base)
        _distribution_files(staging, manifest)
        _write_wheel(staging, Path(wheel_directory) / WHEEL_NAME)
    return WHEEL_NAME


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    with tempfile.TemporaryDirectory(prefix="mara-nltk-metadata-") as temporary:
        name = build_wheel(temporary, config_settings)
        with zipfile.ZipFile(Path(temporary) / name) as wheel:
            for entry in wheel.namelist():
                if entry.startswith(DIST_INFO + "/"):
                    target = Path(metadata_directory) / entry
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(wheel.read(entry))
    return DIST_INFO


def build_sdist(sdist_directory, config_settings=None):
    name = f"nltk-{VERSION}"
    with tarfile.open(Path(sdist_directory) / f"{name}.tar.gz", "w:gz") as archive:
        for filename in (
            "pyproject.toml",
            "backport_build.py",
            "base-files.json",
            "backport.json",
            "security.patch",
            "README.md",
            "LICENSE.txt",
        ):
            archive.add(ROOT / filename, arcname=f"{name}/{filename}")
    return f"{name}.tar.gz"
