import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import gradio as gr
import gradiologin
import pytest
import uvicorn
from fastapi.testclient import TestClient
from ktem import launcher
from ktem.auth.policy import AuthConfigurationError

REPO_ROOT = Path(__file__).resolve().parents[3]


def _sso_module():
    module_spec = importlib.util.find_spec("ktem.sso")
    assert module_spec is not None, "ktem.sso must provide the packaged SSO factory"
    return importlib.import_module("ktem.sso")


def _launch_config(host="0.0.0.0"):
    return launcher.LaunchConfig(auth_mode="sso", host=host, auth=None)


def _fake_mara_app(tmp_path):
    class _FakeMaraApp:
        _favicon = str(tmp_path / "favicon.svg")

        def make(self):
            with gr.Blocks() as blocks:
                gr.Markdown("MARA SSO smoke")
            return blocks

    return _FakeMaraApp


def test_packaged_sso_factory_uses_gradiologin_mount(monkeypatch, tmp_path):
    sso = _sso_module()
    registered = []
    mounted: dict[str, Any] = {}
    mara_app = _fake_mara_app(tmp_path)()
    monkeypatch.setattr(sso, "App", lambda: mara_app)
    monkeypatch.setattr(
        sso,
        "prepare_launch",
        lambda **_kwargs: _launch_config(),
    )
    monkeypatch.setattr(
        gradiologin,
        "register",
        lambda **kwargs: registered.append(kwargs),
    )

    def _mount(app, blocks, path, **kwargs):
        mounted.update(
            app=app,
            blocks=blocks,
            path=path,
            kwargs=kwargs,
        )
        return app

    monkeypatch.setattr(gradiologin, "mount_gradio_app", _mount)
    monkeypatch.setenv("AUTHENTICATION_METHOD", "GOOGLE")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")

    app = sso.create_sso_app(host="0.0.0.0")

    assert app is mounted["app"]
    assert mounted["blocks"] is not None
    assert mounted["path"] == "/app"
    assert str(sso.ASSETS_DIR) in mounted["kwargs"]["allowed_paths"]
    assert registered[0]["name"] == "google"
    assert app.state.mara_app is mara_app


def test_packaged_sso_factory_rejects_non_sso_mode(monkeypatch):
    sso = _sso_module()
    monkeypatch.setattr(
        sso,
        "prepare_launch",
        lambda **_kwargs: launcher.LaunchConfig(
            auth_mode="local",
            host="127.0.0.1",
            auth=None,
        ),
    )

    with pytest.raises(AuthConfigurationError, match="MARA_AUTH_MODE=sso"):
        sso.create_sso_app(host="127.0.0.1")


def test_sso_factory_mount_has_login_route_without_model_services(
    monkeypatch,
    tmp_path,
):
    sso = _sso_module()
    monkeypatch.setattr(sso, "App", _fake_mara_app(tmp_path))
    monkeypatch.setattr(
        sso,
        "prepare_launch",
        lambda **_kwargs: _launch_config(),
    )
    monkeypatch.setattr(gradiologin, "register", lambda **_kwargs: None)
    monkeypatch.setenv("AUTHENTICATION_METHOD", "GOOGLE")
    monkeypatch.setenv("SECRET_KEY", "route-test-secret")

    app = sso.create_sso_app(host="0.0.0.0")

    with TestClient(app) as client:
        root = client.get("/", follow_redirects=False)
        assert root.status_code in {302, 307}
        assert root.headers["location"] == "login"
        assert client.get("/login").status_code == 200


def test_packaged_launcher_dispatches_sso_to_uvicorn(monkeypatch, tmp_path):
    sso = _sso_module()
    config = _launch_config(host="0.0.0.0")
    mara_app = object()
    fastapi_app = SimpleNamespace(state=SimpleNamespace(mara_app=mara_app))
    calls = []
    monkeypatch.setattr(launcher, "prepare_launch", lambda **_kwargs: config)
    monkeypatch.setattr(sso, "create_sso_app", lambda **_kwargs: fastapi_app)
    monkeypatch.setattr(
        uvicorn,
        "run",
        lambda app, **kwargs: calls.append((app, kwargs)),
    )
    monkeypatch.setattr(
        launcher,
        "App",
        lambda: pytest.fail("SSO launch must not use Blocks.launch"),
    )

    result = launcher.launch_app(host="0.0.0.0", port=9000, inbrowser=False)

    assert result is mara_app
    assert calls == [(fastapi_app, {"host": "0.0.0.0", "port": 9000})]


def test_root_sso_module_is_a_thin_package_factory_wrapper():
    source = (REPO_ROOT / "sso_app.py").read_text(encoding="utf-8")

    assert "from ktem.sso import create_sso_app" in source
    assert "app = create_sso_app(" in source
    assert "gradiologin" not in source
    assert "FastAPI" not in source
    assert "from ktem.main import App" not in source


def test_container_sso_selection_accepts_canonical_mode():
    source = (REPO_ROOT / "launch.sh").read_text(encoding="utf-8")

    assert '"$MARA_AUTH_MODE" = "sso"' in source
    assert "sso_app:app" in source
