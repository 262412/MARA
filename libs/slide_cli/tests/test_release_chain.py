from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_publish_module():
    module_path = REPO_ROOT / "scripts" / "publish_packages.py"
    spec = importlib.util.spec_from_file_location("publish_packages", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_publish_script_includes_slide_cli_in_dependency_order():
    publish_packages = _load_publish_module()

    assert [package.name for package in publish_packages.PACKAGE_ORDER] == [
        "ktem",
        "kotaemon",
        "slide-cli",
        "kotaemon-app",
    ]


def test_root_package_exposes_slide_cli_optional_extra():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "[project.optional-dependencies]" in pyproject
    assert 'slide = ["slide-cli"]' in pyproject


def test_release_docs_cover_direct_slide_cli_publish_and_install():
    root_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    package_readme = (REPO_ROOT / "libs" / "slide_cli" / "README.md").read_text(
        encoding="utf-8"
    )
    workflow = (REPO_ROOT / ".github" / "workflows" / "publish-packages.yaml").read_text(
        encoding="utf-8"
    )

    assert "pip install slide-cli" in root_readme
    assert "testpypi" in root_readme.lower()
    assert "pip install slide-cli" in package_readme
    assert "ktem -> kotaemon -> slide-cli -> kotaemon-app" in workflow


def test_phase2_docs_cover_slide_docqa_mainline_boundary():
    root_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    package_readme = (REPO_ROOT / "libs" / "slide_cli" / "README.md").read_text(
        encoding="utf-8"
    )
    release_doc = (REPO_ROOT / "docs" / "slide_cli_release.md").read_text(
        encoding="utf-8"
    )

    for content in [root_readme, package_readme, release_doc]:
        assert "slide docqa delete" in content

    assert "slide-docqa-delete" in root_readme
    assert "maintainer" in release_doc.lower()
    assert "slide docqa acceptance" in release_doc


def test_phase3_docs_cover_two_line_slide_model():
    root_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    package_readme = (REPO_ROOT / "libs" / "slide_cli" / "README.md").read_text(
        encoding="utf-8"
    )
    release_doc = (REPO_ROOT / "docs" / "slide_cli_release.md").read_text(
        encoding="utf-8"
    )
    phase3_plan = (
        REPO_ROOT
        / "docs"
        / "superpowers"
        / "plans"
        / "2026-04-22-slide-cli-phase3-foundation.md"
    ).read_text(encoding="utf-8")

    assert "`slide ...` is the product line entrypoint" in root_readme
    assert "`slide docqa ...` is the focused DocQA surface" in root_readme
    assert "The phase-3 shell is split into two lines:" in package_readme
    assert "`slide ...` is the high-permission product line" in package_readme
    for command in [
        "slide inspect",
        "slide read-slide",
        "slide extract",
        "slide search",
        "slide files",
        "slide read",
        "slide write",
        "slide delete",
        "slide shell",
    ]:
        assert command in root_readme
        assert command in package_readme
        assert command in release_doc
    assert "slide docqa ..." in package_readme
    assert (
        "Phase 3 keeps the user-facing shell intentionally split into two lines"
        in release_doc
    )
    assert "`slide docqa ...` is the specialist document-QA line" in release_doc
    assert "two-line model" in phase3_plan
