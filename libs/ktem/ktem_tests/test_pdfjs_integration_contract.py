from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from ktem import launcher
from ktem.assets.pdfjs_assets import PdfJsAssetError, materialize_pdfjs

REPO_ROOT = Path(__file__).resolve().parents[3]
ARCHIVE_PATH = "libs/ktem/ktem/assets/vendor/pdfjs/pdfjs-6.1.200-dist.zip"


def test_launcher_allows_the_runtime_pdfjs_directory(monkeypatch, tmp_path):
    launched = {}

    class _Demo:
        def queue(self):
            return self

        def launch(self, **kwargs):
            launched.update(kwargs)

    class _App:
        _favicon = "favicon.svg"

        def make(self):
            return _Demo()

    app_data_dir = tmp_path / "app-data"
    pdfjs_dir = app_data_dir / "assets" / "pdfjs" / "6.1.200"
    monkeypatch.setenv("KH_APP_DATA_DIR", str(app_data_dir))
    monkeypatch.setattr(
        launcher,
        "prepare_launch",
        lambda **_kwargs: launcher.LaunchConfig(
            auth_mode="local",
            host="127.0.0.1",
            auth=None,
        ),
    )
    monkeypatch.setattr(launcher, "App", _App)
    monkeypatch.setattr(launcher, "ensure_gradio_temp_dir", lambda: str(tmp_path))
    monkeypatch.setattr(
        launcher,
        "flowsettings",
        SimpleNamespace(
            KH_APP_DATA_DIR=app_data_dir,
            KH_DOC_DIR=tmp_path,
            KH_FILESTORAGE_PATH=tmp_path,
            KH_GRADIO_SHARE=False,
        ),
    )

    launcher.launch_app(host="127.0.0.1", port=7860, inbrowser=False)

    assert str(pdfjs_dir.resolve()) in launched["allowed_paths"]


def test_launcher_revalidates_runtime_pdfjs_before_serving_it(tmp_path):
    app_data_dir = tmp_path / "app-data"
    materialization = materialize_pdfjs(app_data_dir=app_data_dir)
    (materialization.path / "web" / "viewer.html").write_text(
        "<script>window.tampered = true</script>",
        encoding="utf-8",
    )

    with pytest.raises(
        PdfJsAssetError,
        match="content hash mismatch.*web/viewer.html",
    ):
        launcher.ensure_pdfjs_runtime_assets(
            settings=SimpleNamespace(KH_APP_DATA_DIR=app_data_dir)
        )


def test_platform_launchers_do_not_download_pdfjs_at_normal_startup():
    for relative_path in (
        "scripts/run_linux.sh",
        "scripts/run_macos.sh",
        "scripts/run_windows.bat",
    ):
        source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert "releases/download/v4.0.379" not in source
        assert "downloading automatically" not in source.lower()
        assert "PDF.js not found, downloading" not in source


def test_platform_launchers_materialize_and_launch_from_one_runtime_root():
    for relative_path in (
        "scripts/run_linux.sh",
        "scripts/run_macos.sh",
        "scripts/run_windows.bat",
    ):
        source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert "KH_APP_DATA_DIR" in source
        assert "ktem.runtime_bootstrap" in source
        assert "ktem.assets.pdfjs_assets" in source


def test_maintainer_refresh_script_is_fixed_to_official_asset_and_hash():
    source = (REPO_ROOT / "scripts" / "download_pdfjs.sh").read_text(encoding="utf-8")

    assert "v6.1.200/pdfjs-6.1.200-dist.zip" in source
    assert "9e1584d768ed099aa4be27ea423f89a038c2005f1ee417ea4f35ba4591ec1846" in source
    assert "sha256sum" in source
    assert "curl --fail" in source


def test_archive_has_exact_docker_and_precommit_allowlists():
    dockerignore = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
    precommit = yaml.safe_load(
        (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    escaped_archive_path = ARCHIVE_PATH.replace(".", r"\.")
    large_file_hook = next(
        hook
        for repository in precommit["repos"]
        for hook in repository["hooks"]
        if hook["id"] == "check-added-large-files"
    )

    assert "*.zip" in dockerignore
    assert f"!{ARCHIVE_PATH}" in dockerignore
    assert large_file_hook["exclude"] == f"^{escaped_archive_path}$"


def test_env_example_exposes_only_the_pinned_pdfjs_version():
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")

    assert 'PDFJS_VERSION_DIST="pdfjs-6.1.200-dist"' in env_example
    assert "pdfjs-4.0.379-dist" not in env_example
