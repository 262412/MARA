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
        "-e ./libs/kotaemon",
        "-e ./libs/ktem",
        "-e ./libs/slide_cli",
    }
    assert expected_editables.issubset(requirement_lines)
    assert "-e ./libs/kotaemon[all]" not in requirement_lines

    for editable in expected_editables:
        package_path = editable.removeprefix("-e ./").split("[", 1)[0]
        assert (REPO_ROOT / package_path / "pyproject.toml").exists()


def test_source_app_binds_to_azure_app_service_port():
    app_source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")

    assert 'os.getenv("PORT"' in app_source
    assert 'server_name="0.0.0.0"' in app_source
    assert "server_port=server_port" in app_source
    assert "inbrowser=False" in app_source
    assert app_source.count("inbrowser=") == 1
