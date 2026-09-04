from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import tomli
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parents[1]

PACKAGES = {
    "mara-app": REPO_ROOT,
    "kotaemon": REPO_ROOT / "libs" / "kotaemon",
    "ktem": REPO_ROOT / "libs" / "ktem",
    "mara-research-cli": REPO_ROOT / "libs" / "slide_cli",
}

DEVELOPER_TOOLS = {
    "black",
    "build",
    "coverage",
    "flake8",
    "ipython",
    "pre-commit",
    "pytest",
    "pytest-mock",
    "ruff",
    "sphinx",
    "twine",
}


def _pyproject(package_root: Path) -> dict:
    return tomli.loads((package_root / "pyproject.toml").read_text(encoding="utf-8"))


def test_root_uses_runtime_only_kotaemon_extra():
    root_project = _pyproject(REPO_ROOT)["project"]
    kotaemon_extras = _pyproject(PACKAGES["kotaemon"])["project"][
        "optional-dependencies"
    ]

    assert "kotaemon[mara-runtime]" in root_project["dependencies"]
    assert not any("kotaemon[all]" in item for item in root_project["dependencies"])
    assert kotaemon_extras["mara-runtime"]
    assert kotaemon_extras["adv"] == ["kotaemon[llama-cpp,mara-runtime]"]
    assert kotaemon_extras["all"] == ["kotaemon[dev,llama-cpp,mara-runtime]"]

    runtime_names = {
        canonicalize_name(Requirement(item).name)
        for item in kotaemon_extras["mara-runtime"]
    }
    assert runtime_names.isdisjoint(DEVELOPER_TOOLS)


def test_compatibility_extras_have_a_bounded_deprecation_notice():
    notice = (PACKAGES["kotaemon"] / "README.md").read_text(encoding="utf-8")

    assert "mara-runtime" in notice
    assert "adv" in notice
    assert "all" in notice
    assert "one release" in notice.lower()
    assert "deprecated" in notice.lower()


def test_all_distributions_use_modern_apache_metadata_and_ship_legal_files():
    for package_name, package_root in PACKAGES.items():
        config = _pyproject(package_root)
        project = config["project"]
        build_requirements = config["build-system"]["requires"]

        assert project["license"] == "Apache-2.0", package_name
        assert project["license-files"] == ["LICENSE.txt", "NOTICE"], package_name
        assert not any(
            item == "License :: OSI Approved :: Apache Software License"
            for item in project.get("classifiers", [])
        ), package_name
        assert build_requirements == [
            "setuptools==80.9.0",
            "wheel==0.45.1",
            "setuptools-git-versioning==2.1.0",
        ], package_name
        assert (package_root / "LICENSE.txt").is_file(), package_name
        assert (package_root / "NOTICE").is_file(), package_name


def test_notices_identify_mara_and_pdfjs_without_stale_slides_branding():
    for package_name, package_root in PACKAGES.items():
        notice = (package_root / "NOTICE").read_text(encoding="utf-8")

        assert "MARA" in notice, package_name
        assert "Slides" not in notice, package_name
        assert "Mozilla PDF.js" in notice, package_name
        assert "v6.1.200" in notice, package_name
        assert "https://github.com/mozilla/pdf.js" in notice, package_name
        assert "Apache License" in notice, package_name


def test_ktem_legacy_requirements_shim_cannot_drift_from_package_metadata():
    assert not (PACKAGES["ktem"] / "requirements.txt").exists()


def test_ktem_declares_its_kotaemon_runtime_dependency():
    dependencies = _pyproject(PACKAGES["ktem"])["project"]["dependencies"]
    dependency_names = {
        canonicalize_name(Requirement(item).name) for item in dependencies
    }

    assert "kotaemon" in dependency_names


def test_constraints_are_a_marker_preserving_export_of_locked_runtime_versions():
    constraints_path = REPO_ROOT / "constraints.txt"
    lines = constraints_path.read_text(encoding="utf-8").splitlines()
    expected_command = (
        "uv export --locked --all-packages --no-dev --no-hashes --no-emit-workspace "
        "--no-header --no-annotate"
    )
    assert lines[:3] == [
        "# Generated from uv.lock. Do not edit by hand.",
        f"# Regenerate: {expected_command} > constraints.txt",
        "# Verify: python scripts/sync_locked_constraints.py --check",
    ]

    lock = tomli.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    locked_versions: dict[str, set[str]] = defaultdict(set)
    for package in lock["package"]:
        if "version" in package:
            locked_versions[canonicalize_name(package["name"])].add(package["version"])

    requirements = [
        Requirement(line)
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert requirements
    # `build` is a declared chromadb runtime dependency and Gradio 4.39
    # declares `ruff`; the remaining first-party development group must not
    # leak through the deprecated `all` extra.
    transitive_runtime_tools = {"build", "ruff"}
    assert not {canonicalize_name(req.name) for req in requirements} & (
        DEVELOPER_TOOLS - transitive_runtime_tools
    )
    for requirement in requirements:
        pins = [
            specifier.version
            for specifier in requirement.specifier
            if specifier.operator == "=="
        ]
        assert len(pins) == 1, str(requirement)
        assert pins[0] in locked_versions[canonicalize_name(requirement.name)], str(
            requirement
        )


def test_constraints_sync_command_is_part_of_the_quality_gate():
    workflow = (REPO_ROOT / ".github" / "workflows" / "quality-gates.yaml").read_text(
        encoding="utf-8"
    )

    assert "scripts/sync_locked_constraints.py --check" in workflow


def test_clean_wheel_smoke_does_not_select_deprecated_all_extra():
    smoke = (REPO_ROOT / "scripts" / "run_clean_wheel_smoke.py").read_text(
        encoding="utf-8"
    )

    assert '"--all-extras"' not in smoke
    assert "--no-dev" in smoke
