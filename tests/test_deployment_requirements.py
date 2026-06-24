from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_root_requirements_file_keeps_azure_app_service_build_installable():
    requirements = REPO_ROOT / "requirements.txt"

    assert requirements.exists()

    requirement_lines = {
        line.strip()
        for line in requirements.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    expected_editables = {
        "-e ./libs/kotaemon[all]",
        "-e ./libs/ktem",
        "-e ./libs/slide_cli",
    }
    assert expected_editables.issubset(requirement_lines)

    for editable in expected_editables:
        package_path = editable.removeprefix("-e ./").split("[", 1)[0]
        assert (REPO_ROOT / package_path / "pyproject.toml").exists()
