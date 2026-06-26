from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_root_requirements_file_keeps_azure_app_service_build_installable():
    requirements = REPO_ROOT / "requirements.txt"
    requirements_source = REPO_ROOT / "requirements.azure.in"
    constraints = REPO_ROOT / "constraints.txt"

    assert requirements.exists()
    assert requirements_source.exists()
    assert constraints.exists()

    requirement_lines = {
        line.strip()
        for line in requirements.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    source_lines = {
        line.strip()
        for line in requirements_source.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    constraint_lines = {
        line.strip()
        for line in constraints.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    expected_local_packages = {
        "./libs/kotaemon",
        "./libs/ktem",
        "./libs/slide_cli",
    }
    expected_pins = {
        "huggingface-hub<1.0",
        "langchain<0.3",
        "langchain-community<0.3",
        "langchain-core<0.3",
        "numpy==1.26.4",
        "ollama==0.6.2",
        "onnxruntime==1.23.2",
        "opentelemetry-instrumentation-fastapi==0.48b0",
    }
    assert "-c constraints.txt" in requirement_lines
    assert "-r requirements.azure.in" in requirement_lines
    assert expected_local_packages.issubset(source_lines)
    assert "huggingface-hub<1.0" in source_lines
    assert "langchain<0.3" in source_lines
    assert "langchain-community<0.3" in source_lines
    assert "langchain-core<0.3" in source_lines
    assert not any(line.startswith("-e ") for line in requirement_lines)
    assert not any(line.startswith("-e ") for line in source_lines)
    assert "-e ./libs/kotaemon[all]" not in requirement_lines
    assert "-e ./libs/kotaemon[all]" not in source_lines
    source_only_pins = {
        "huggingface-hub<1.0",
        "langchain<0.3",
        "langchain-community<0.3",
        "langchain-core<0.3",
    }
    assert expected_pins - source_only_pins <= constraint_lines
    assert any(line.startswith("huggingface-hub==0.") for line in constraint_lines)
    assert not any(line.startswith("huggingface-hub==1.") for line in constraint_lines)
    assert any(line.startswith("langchain==0.2.") for line in constraint_lines)
    assert not any(line.startswith("langchain==1.") for line in constraint_lines)
    assert any(
        line.startswith("langchain-community==0.2.") for line in constraint_lines
    )
    assert not any(
        line.startswith("langchain-community==0.4.") for line in constraint_lines
    )
    assert any(line.startswith("langchain-core==0.2.") for line in constraint_lines)
    assert not any(line.startswith("langchain-core==1.") for line in constraint_lines)
    assert not any(line.startswith("-e ") for line in constraint_lines)

    for package_path in expected_local_packages:
        assert (REPO_ROOT / package_path / "pyproject.toml").exists()


def test_source_app_binds_to_azure_app_service_port():
    app_source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")

    assert 'os.getenv("WEBSITE_SITE_NAME")' in app_source
    assert 'os.environ.setdefault("KH_APP_DATA_DIR", "/home/site/mara_data")' in (
        app_source
    )
    assert 'os.getenv("PORT"' in app_source
    assert 'server_name="0.0.0.0"' in app_source
    assert "server_port=server_port" in app_source
    assert 'os.getenv("PORT", "8000")' in app_source
    assert "inbrowser=False" in app_source
    assert app_source.count("inbrowser=") == 1
    assert "MARA Azure startup" in app_source
    assert "from ktem.launcher import ensure_gradio_temp_dir" not in app_source
