"""Assemble the Windows reviewer ZIP from built wheels and a frozen export."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from email import message_from_bytes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "packaging" / "reviewer"
UV_VERSION = "0.11.19"
PYTHON_VERSION = "3.10.19"
UV_WHEEL_SHA256 = "480fc34a8d0967af6a90b3f99a6e5687cd5c6e29528de96bec04d6e305a59363"
PACKAGES = ("kotaemon", "ktem", "mara-research-cli", "mara-app")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        result = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def wheel_identity(path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(path) as archive:
        metadata = [p for p in archive.namelist() if p.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError(f"Expected unique METADATA in {path.name}")
        message = message_from_bytes(archive.read(metadata[0]))
    name = re.sub(r"[-_.]+", "-", str(message["Name"])).lower()
    return name, str(message["Version"])


def vendor_requirements(text: str, wheels: list[Path]) -> str:
    replacements = {
        wheel_identity(p)[0]: (wheel_identity(p)[1], digest(p)) for p in wheels
    }
    blocks = re.split(r"\n(?=[a-zA-Z0-9])", text.strip())
    used = set()
    result = []
    for block in blocks:
        first = block.split("\\\n")[0].strip().split(" --hash=")[0]
        match = re.match(r"([\w.-]+)==([^ ;]+)", first)
        if match and match[1] in replacements:
            version, checksum = replacements[match[1]]
            if match[2] != version:
                raise ValueError(f"{match[1]} wheel disagrees with locked version")
            block = f"{first} \\\n    --hash=sha256:{checksum}"
            used.add(match[1])
        result.append(block)
    if used != set(replacements):
        raise ValueError(f"Vendor wheels absent from lock: {set(replacements) - used}")
    return "\n".join(result) + "\n"


def extract_uv(source: Path, destination: Path) -> None:
    if digest(source) != UV_WHEEL_SHA256:
        raise ValueError(
            "uv wheel SHA-256 does not match the pinned official PyPI wheel"
        )
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        executable = [p for p in archive.namelist() if p.endswith("/scripts/uv.exe")]
        if len(executable) != 1:
            raise ValueError("uv wheel has no unique uv.exe")
        (destination / "uv.exe").write_bytes(archive.read(executable[0]))
        licenses = [p for p in archive.namelist() if ".dist-info/licenses/" in p]
        if not licenses:
            raise ValueError("uv wheel has no license files")
        for name in licenses:
            if not name.endswith("/"):
                target = (
                    destination / "licenses" / name.split(".dist-info/licenses/", 1)[1]
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))


def file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): digest(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def copy_wheels(dist_root: Path, destination: Path) -> tuple[list[Path], list[Path]]:
    destination.mkdir()
    app_wheels = []
    for package in PACKAGES:
        candidates = list((dist_root / package).glob("*.whl"))
        if len(candidates) != 1 or wheel_identity(candidates[0])[0] != package:
            raise ValueError(f"Expected exactly one {package} wheel in {dist_root}")
        app_wheels.append(Path(shutil.copy2(candidates[0], destination)))
    vendor = [
        Path(shutil.copy2(p, destination))
        for p in sorted((dist_root / "vendor").glob("*.whl"))
    ]
    return app_wheels, vendor


def assemble(args: argparse.Namespace) -> Path:
    output = args.output_dir.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Store generated bundles outside the Git checkout")
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_commit):
        raise ValueError("--source-commit must be the full application source commit")
    output.mkdir(parents=True, exist_ok=True)
    name = f"MARA-reviewer-windows-x64-{args.source_commit[:8]}"
    archive_path = output / f"{name}.zip"
    if archive_path.exists():
        raise FileExistsError(f"Refusing to overwrite {archive_path}")
    with tempfile.TemporaryDirectory(prefix="reviewer-stage-", dir=output) as temporary:
        bundle = Path(temporary) / name
        shutil.copytree(TEMPLATE, bundle)
        app_wheels, vendor = copy_wheels(args.dist_root, bundle / "wheels")
        extract_uv(args.uv_wheel, bundle / "tools")
        runtime_lock = args.requirements.read_text(encoding="utf-8")
        (bundle / "runtime-requirements.txt").write_text(
            vendor_requirements(runtime_lock, vendor), encoding="utf-8"
        )
        (bundle / "application-requirements.txt").write_text(
            "\n".join(
                f"./wheels/{p.name} --hash=sha256:{digest(p)}" for p in app_wheels
            )
            + "\n",
            encoding="utf-8",
        )
        for legal in ("LICENSE.txt", "NOTICE"):
            shutil.copy2(ROOT / legal, bundle / legal)
        manifest = {
            "schema_version": 1,
            "bundle_id": name,
            "platform": "windows-x86_64",
            "source_commit": args.source_commit,
            "base_main_commit": args.base_main_commit,
            "python_version": PYTHON_VERSION,
            "uv_version": UV_VERSION,
            "uv_wheel_sha256": UV_WHEEL_SHA256,
            "original_requirements_sha256": digest(args.requirements),
            "application_versions": dict(wheel_identity(p) for p in app_wheels),
            "files": file_hashes(bundle),
        }
        (bundle / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        with zipfile.ZipFile(
            archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            for path in sorted(bundle.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(bundle.parent).as_posix())
    archive_path.with_suffix(".zip.sha256").write_text(
        f"{digest(archive_path)}  {archive_path.name}\n", encoding="utf-8"
    )
    return archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dist-root", "requirements", "uv-wheel", "output-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--base-main-commit", required=True)
    print(assemble(parser.parse_args()))


if __name__ == "__main__":
    main()
