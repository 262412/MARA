from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import tomli

REPO_ROOT = Path(__file__).resolve().parents[1]
KTEM_ROOT = REPO_ROOT / "libs" / "ktem"


def test_ktem_declares_apache_license_and_distribution_files():
    project = tomli.loads(
        (KTEM_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]

    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE.txt", "NOTICE"]
    assert "License :: OSI Approved :: Apache Software License" in project[
        "classifiers"
    ]
    assert (KTEM_ROOT / "LICENSE.txt").is_file()
    assert (KTEM_ROOT / "NOTICE").is_file()


def test_ktem_wheel_contains_icons_help_pdfjs_and_legal_files(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(tmp_path),
            str(KTEM_ROOT),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheel_path = next(tmp_path.glob("ktem-*.whl"))

    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())
        metadata_name = next(
            name for name in names if name.endswith(".dist-info/METADATA")
        )
        metadata = wheel.read(metadata_name).decode("utf-8")

    expected_assets = {
        "ktem/assets/icons/delete.svg",
        "ktem/assets/icons/sidebar.svg",
        "ktem/assets/md/about.md",
        "ktem/assets/md/usage.md",
        "ktem/assets/vendor/pdfjs/LICENSE.pdfjs",
        "ktem/assets/vendor/pdfjs/manifest.json",
        "ktem/assets/vendor/pdfjs/pdfjs-6.1.200-dist.zip",
    }
    assert expected_assets <= names
    assert any(name.endswith(".dist-info/licenses/LICENSE.txt") for name in names)
    assert any(name.endswith(".dist-info/licenses/NOTICE") for name in names)
    assert "License-Expression: Apache-2.0" in metadata
    assert "Classifier: License :: OSI Approved :: Apache Software License" in metadata
