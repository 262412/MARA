from __future__ import annotations

import inspect
import io
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


def _write_sdist(path: Path, members: list[tuple[str, bytes]]) -> None:
    with tarfile.open(path, mode="w:gz") as archive:
        for name, content in members:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))


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


def test_sdist_validator_selects_root_metadata_over_egg_info_copy(tmp_path):
    sdist = tmp_path / "mara_app-1.0.tar.gz"
    _write_sdist(
        sdist,
        [
            ("mara_app-1.0/LICENSE.txt", b"license"),
            ("mara_app-1.0/NOTICE", b"notice"),
            (
                "mara_app-1.0/PKG-INFO",
                b"Metadata-Version: 2.4\nLicense-Expression: Apache-2.0\n",
            ),
            (
                "mara_app-1.0/mara_app.egg-info/PKG-INFO",
                b"Metadata-Version: 2.4\n",
            ),
        ],
    )

    run_clean_wheel_smoke.validate_sdist_contents({"mara-app": sdist})


def test_sdist_validator_rejects_missing_root_metadata(tmp_path):
    sdist = tmp_path / "mara_app-1.0.tar.gz"
    _write_sdist(
        sdist,
        [
            ("mara_app-1.0/LICENSE.txt", b"license"),
            ("mara_app-1.0/NOTICE", b"notice"),
            (
                "mara_app-1.0/mara_app.egg-info/PKG-INFO",
                b"Metadata-Version: 2.4\nLicense-Expression: Apache-2.0\n",
            ),
        ],
    )

    with pytest.raises(RuntimeError, match="root PKG-INFO"):
        run_clean_wheel_smoke.validate_sdist_contents({"mara-app": sdist})


def test_sdist_validator_rejects_duplicate_root_metadata(tmp_path):
    sdist = tmp_path / "mara_app-1.0.tar.gz"
    root_metadata = (
        "mara_app-1.0/PKG-INFO",
        b"Metadata-Version: 2.4\nLicense-Expression: Apache-2.0\n",
    )
    _write_sdist(
        sdist,
        [
            ("mara_app-1.0/LICENSE.txt", b"license"),
            ("mara_app-1.0/NOTICE", b"notice"),
            root_metadata,
            root_metadata,
        ],
    )

    with pytest.raises(RuntimeError, match="root PKG-INFO"):
        run_clean_wheel_smoke.validate_sdist_contents({"mara-app": sdist})


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


def test_smoke_environment_discards_external_pythonpath(monkeypatch):
    monkeypatch.setenv(
        "PYTHONPATH",
        "/checkout/libs/ktem:/checkout/libs/kotaemon:/checkout/libs/slide_cli",
    )
    monkeypatch.setenv("PYTHONHOME", "/checkout/python")
    monkeypatch.setenv("PYTHONSTARTUP", "/checkout/startup.py")
    monkeypatch.setenv("VIRTUAL_ENV", "/checkout/.venv")
    clean_environment = getattr(run_clean_wheel_smoke, "_clean_environment", None)

    assert callable(clean_environment)
    clean = clean_environment()
    for variable in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "VIRTUAL_ENV"):
        assert variable not in clean


def test_offline_environment_contains_only_guard_pythonpath(tmp_path):
    offline = run_clean_wheel_smoke._offline_environment(
        tmp_path,
        {"PYTHONPATH": "/checkout/libs/ktem", "PATH": "/usr/bin"},
    )

    assert offline["PYTHONPATH"] == str(tmp_path / "offline-guard")


def test_layer_imports_use_isolated_layer_venv_before_fresh_offline_phase():
    install_source = inspect.getsource(run_clean_wheel_smoke._install_wheel_layers)
    offline_source = inspect.getsource(run_clean_wheel_smoke._run_offline_runtime_smoke)
    run_source = inspect.getsource(run_clean_wheel_smoke.run_smoke)

    assert "_run_layer_imports" in install_source
    assert "_run_layer_imports" not in offline_source
    assert "_assert_installed_distribution_paths" in offline_source
    assert "layer-venv" in run_source
    assert "combined-venv" in run_source


def test_offline_runtime_verifies_modules_are_loaded_from_venv():
    assert callable(
        getattr(run_clean_wheel_smoke, "_assert_installed_distribution_paths", None)
    )
    source = inspect.getsource(
        run_clean_wheel_smoke._assert_installed_distribution_paths
    )
    layer_source = inspect.getsource(run_clean_wheel_smoke._run_layer_imports)

    assert "PACKAGE_ORDER" in source
    assert "sys.prefix" in source
    assert "sys.prefix" in layer_source
    assert "__file__" in layer_source


def test_command_runner_uses_an_explicit_non_repository_cwd(monkeypatch, tmp_path):
    captured = {}

    def capture_run(*_args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(run_clean_wheel_smoke.subprocess, "run", capture_run)
    run_clean_wheel_smoke._run(
        ["python", "-c", "pass"],
        env={},
        cwd=tmp_path,
    )

    assert captured["cwd"] == tmp_path
    assert captured["cwd"] != REPO_ROOT


def test_only_locked_export_runs_from_repository_root():
    export_source = inspect.getsource(run_clean_wheel_smoke._export_constraints)
    layer_source = inspect.getsource(run_clean_wheel_smoke._run_layer_imports)
    metadata_source = inspect.getsource(
        run_clean_wheel_smoke._assert_installed_distribution_paths
    )
    offline_source = inspect.getsource(run_clean_wheel_smoke._run_offline_runtime_smoke)

    assert "cwd=REPO_ROOT" in export_source
    for source in (layer_source, metadata_source, offline_source):
        assert "cwd=venv.parent" in source
