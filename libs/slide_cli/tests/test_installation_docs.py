from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_windows_installer_installs_mara_cli_from_local_implementation():
    install_script = (REPO_ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "uv sync" in install_script
    assert "--frozen" in install_script
    assert "--extra mara" in install_script
    assert "MARA.exe" in install_script
    assert "pip install" not in install_script
    assert "UV_PYTHON_DOWNLOADS" in install_script
    assert "uv python find" in install_script
    assert "Run '$venvMARA app run' to launch the Web UI." in install_script
    assert (
        "Run '$venvMARA docqa doctor' to validate the shared DocQA runtime."
        in install_script
    )


def test_posix_installer_installs_mara_cli_from_local_implementation():
    install_script = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")

    assert "uv sync" in install_script
    assert "--frozen" in install_script
    assert "--extra mara" in install_script
    assert "/bin/MARA" in install_script
    assert "pip install" not in install_script
    assert "UV_PYTHON_DOWNLOADS" in install_script
    assert "uv python find" in install_script
    assert "Run '$VENV_MARA app run' to launch the Web UI." in install_script
    assert (
        "Run '$VENV_MARA docqa doctor' to validate the shared DocQA runtime."
        in install_script
    )


def test_root_readme_documents_mara_research_cli_source_install():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "uv sync --extra mara" in readme
    assert 'pip install -e "libs/slide_cli"' not in readme
    assert "pip install mara-research-cli" in readme
    assert "MARA doctor" in readme
