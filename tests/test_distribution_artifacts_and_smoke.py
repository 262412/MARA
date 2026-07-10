from __future__ import annotations

import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts import run_clean_wheel_smoke

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGES = {
    "mara-app": REPO_ROOT,
    "kotaemon": REPO_ROOT / "libs" / "kotaemon",
    "ktem": REPO_ROOT / "libs" / "ktem",
    "mara-research-cli": REPO_ROOT / "libs" / "slide_cli",
}


def _build(
    package_name: str, package_root: Path, output_root: Path
) -> tuple[Path, Path]:
    output = output_root / package_name
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--sdist",
            "--wheel",
            "--outdir",
            str(output),
            str(package_root),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    source_prefix = package_name.replace("-", "_")
    staging_debris = sorted(package_root.glob(f"{source_prefix}-[0-9]*"))
    assert not staging_debris, staging_debris
    return next(output.glob("*.whl")), next(output.glob("*.tar.gz"))


def test_four_distribution_artifacts_have_apache_metadata_and_legal_files(tmp_path):
    for package_name, package_root in PACKAGES.items():
        wheel_path, sdist_path = _build(package_name, package_root, tmp_path)

        with zipfile.ZipFile(wheel_path) as wheel:
            wheel_names = set(wheel.namelist())
            metadata_name = next(
                name for name in wheel_names if name.endswith(".dist-info/METADATA")
            )
            metadata = wheel.read(metadata_name).decode("utf-8")
        assert "License-Expression: Apache-2.0" in metadata, package_name
        assert any(
            name.endswith(".dist-info/licenses/LICENSE.txt") for name in wheel_names
        ), package_name
        assert any(
            name.endswith(".dist-info/licenses/NOTICE") for name in wheel_names
        ), package_name

        with tarfile.open(sdist_path, mode="r:gz") as sdist:
            sdist_names = {Path(name).name for name in sdist.getnames()}
        assert {"LICENSE.txt", "NOTICE"} <= sdist_names, package_name


def test_wheel_validator_rejects_artifact_without_legal_files(tmp_path):
    wheels = {}
    for package_name, package_prefix in run_clean_wheel_smoke.EXPECTED_WHEELS.items():
        wheel = tmp_path / f"{package_name}.whl"
        with zipfile.ZipFile(wheel, mode="w") as archive:
            archive.writestr(
                f"{package_name}.dist-info/METADATA",
                "Metadata-Version: 2.4\nLicense-Expression: Apache-2.0\n",
            )
            if package_prefix != ".dist-info/":
                archive.writestr(f"{package_prefix}__init__.py", "")
        wheels[package_name] = wheel

    with pytest.raises(RuntimeError, match="LICENSE"):
        run_clean_wheel_smoke.validate_wheel_contents(wheels)


def test_distribution_smoke_validates_sdists_and_offline_app_init():
    smoke_source = (REPO_ROOT / "scripts" / "run_clean_wheel_smoke.py").read_text(
        encoding="utf-8"
    )

    assert callable(getattr(run_clean_wheel_smoke, "validate_sdist_contents", None))
    assert '"--all-packages"' in smoke_source
    assert '"--all-extras"' not in smoke_source
    assert '"app", "init"' in smoke_source
    assert "sitecustomize.py" in smoke_source
    assert "viewer.html" in smoke_source
    assert "pip check" in smoke_source
    assert '"MARA", "MARA-cli"' in smoke_source
    assert '"docqa", "--help"' in smoke_source
    assert '"app", "--help"' in smoke_source


def test_clean_layer_smoke_imports_representative_installed_modules():
    layer_imports = getattr(run_clean_wheel_smoke, "LAYER_IMPORTS", {})

    assert layer_imports["kotaemon"] == ("kotaemon",)
    assert layer_imports["ktem"] == ("ktem.index.file.pipelines",)
    assert layer_imports["mara-research-cli"] == ("slide_cli.cli",)
    assert callable(getattr(run_clean_wheel_smoke, "_run_layer_imports", None))
