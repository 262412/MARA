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
