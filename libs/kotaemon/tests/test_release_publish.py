from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_ktem_package_has_readme():
    repo_root = _repo_root()
    readme_path = repo_root / "libs" / "ktem" / "README.md"

    assert readme_path.exists()
    content = readme_path.read_text(encoding="utf-8")
    assert "ktem" in content.lower()
    assert "kotaemon" in content.lower()


def test_publish_script_exists_and_releases_three_packages():
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "publish_packages.py"

    assert script_path.exists()
    content = script_path.read_text(encoding="utf-8")
    for token in [
        "ktem",
        "kotaemon",
        "kotaemon-app",
        "--repository",
        "testpypi",
        "pypi",
        "twine",
        "build",
    ]:
        assert token in content


def test_kotaemon_app_package_has_readme_metadata():
    repo_root = _repo_root()
    pyproject_path = repo_root / "pyproject.toml"

    content = pyproject_path.read_text(encoding="utf-8")
    assert 'readme = "README.md"' in content


def test_publish_wrappers_exist():
    repo_root = _repo_root()

    assert (repo_root / "scripts" / "publish_packages.ps1").exists()
    assert (repo_root / "scripts" / "publish_packages.sh").exists()


def test_publish_workflow_exists_and_uploads_in_order():
    repo_root = _repo_root()
    workflow_path = repo_root / ".github" / "workflows" / "publish-packages.yaml"

    assert workflow_path.exists()
    content = workflow_path.read_text(encoding="utf-8")
    for token in [
        "workflow_dispatch",
        "push:",
        "refs/tags/v",
        "TEST_PYPI_API_TOKEN",
        "PYPI_API_TOKEN",
        "scripts/publish_packages.py",
        "--repository testpypi",
        "--repository pypi",
        "ktem",
        "kotaemon",
        "kotaemon-app",
    ]:
        assert token in content
