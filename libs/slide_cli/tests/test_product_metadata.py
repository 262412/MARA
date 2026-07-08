from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_product_package_metadata_uses_mara_identity():
    root_pyproject = _read("pyproject.toml")
    cli_pyproject = _read("libs/slide_cli/pyproject.toml")
    ktem_pyproject = _read("libs/ktem/pyproject.toml")

    assert 'name = "mara-app"' in root_pyproject
    assert (
        'description = "MARA local-first multimodal document QA workbench."'
        in root_pyproject
    )
    assert 'name = "mara-research-cli"' in cli_pyproject
    assert (
        'description = "MARA application runtime and local document QA workbench UI."'
        in ktem_pyproject
    )
    for content in (root_pyproject, cli_pyproject, ktem_pyproject):
        assert "https://github.com/262412/MARA/" in content
        assert "https://github.com/Cinnamon/kotaemon/" in content
        assert "john@cinnamon.is" not in content
        assert "ian@cinnamon.is" not in content


def test_quick_start_documents_single_local_app_port_default():
    readme = _read("README.md")

    assert "The local default is\n`http://localhost:7860/`" in readme
    assert "本地默认是\n`http://localhost:7860/`" in readme
    assert "GRADIO_SERVER_PORT" in readme
    assert "platform `PORT`" in readme
