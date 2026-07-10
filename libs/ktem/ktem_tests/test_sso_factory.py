import importlib
import importlib.util
import inspect
import json
from base64 import b64encode
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import gradio as gr
import gradiologin
import pytest
import uvicorn
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from ktem import launcher
from ktem.auth.policy import AuthConfigurationError

REPO_ROOT = Path(__file__).resolve().parents[3]


def _fake_secret(label: str) -> str:
    return f"test-only-{label}-" + ("x" * 40)


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


def _callback_mara_app(tmp_path, callback_calls):
    class _CallbackMaraApp:
        _favicon = str(tmp_path / "favicon.svg")

        def make(self):
            def _predict(value):
                callback_calls.append(value)
                return f"handled:{value}"

            with gr.Blocks() as blocks:
                value = gr.Textbox()
                output = gr.Textbox()
                gr.Button("Run").click(
                    _predict,
                    inputs=value,
                    outputs=output,
                    api_name="predict",
                )
            return blocks

    return _CallbackMaraApp


def _signed_session_cookie(secret_key, claim):
    payload = b64encode(json.dumps({"user": claim}).encode("utf-8"))
    return TimestampSigner(secret_key).sign(payload).decode("utf-8")


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
    assert mounted["kwargs"]["secret_key"] != "some-secret-string"
    assert mounted["kwargs"]["auth_dependency"] is sso.sso_auth_dependency
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
    monkeypatch.setenv("SECRET_KEY", _fake_secret("route"))

    app = sso.create_sso_app(host="0.0.0.0")

    with TestClient(app) as client:
        root = client.get("/", follow_redirects=False)
        assert root.status_code in {302, 307}
        assert root.headers["location"] == "/login"
        assert client.get("/login").status_code == 200


def test_sso_predict_route_rejects_unauthenticated_callback(monkeypatch, tmp_path):
    sso = _sso_module()
    callback_calls: list[str] = []
    monkeypatch.setattr(sso, "App", _callback_mara_app(tmp_path, callback_calls))
    monkeypatch.setattr(sso, "prepare_launch", lambda **_kwargs: _launch_config())
    monkeypatch.setattr(gradiologin, "register", lambda **_kwargs: None)
    monkeypatch.setenv("AUTHENTICATION_METHOD", "GOOGLE")
    monkeypatch.setenv("SECRET_KEY", _fake_secret("predict-route"))
    app = sso.create_sso_app(host="0.0.0.0")

    with TestClient(app) as client:
        response = client.post(
            "/app/api/predict",
            json={"data": ["blocked"], "fn_index": 0, "session_hash": "test"},
        )

    assert response.status_code == 401
    assert callback_calls == []


def test_sso_predict_route_accepts_signed_provider_session(monkeypatch, tmp_path):
    sso = _sso_module()
    callback_calls: list[str] = []
    secret_key = _fake_secret("authenticated-route")
    monkeypatch.setattr(sso, "App", _callback_mara_app(tmp_path, callback_calls))
    monkeypatch.setattr(sso, "prepare_launch", lambda **_kwargs: _launch_config())
    monkeypatch.setattr(gradiologin, "register", lambda **_kwargs: None)
    monkeypatch.setenv("AUTHENTICATION_METHOD", "GOOGLE")
    monkeypatch.setenv("SECRET_KEY", secret_key)
    app = sso.create_sso_app(host="0.0.0.0")

    with TestClient(app) as client:
        client.cookies.set(
            "session",
            _signed_session_cookie(
                secret_key,
                {"sub": "provider-subject", "email": "person@example.test"},
            ),
        )
        response = client.post(
            "/app/api/predict",
            json={"data": ["allowed"], "fn_index": 0, "session_hash": "test"},
        )

    assert response.status_code == 200
    assert response.json()["data"] == ["handled:allowed"]
    assert callback_calls == ["allowed"]


def test_sso_factory_has_no_prepared_config_bypass():
    sso = _sso_module()

    assert "launch_config" not in inspect.signature(sso.create_sso_app).parameters


@pytest.mark.parametrize(
    "weak_secret",
    [
        "some-secret-string",
        "default-secret-key",
        "short-secret",
        "a" * 64,
    ],
)
def test_sso_factory_rejects_weak_configured_session_secret(
    monkeypatch,
    weak_secret,
):
    sso = _sso_module()
    monkeypatch.setenv("SECRET_KEY", weak_secret)

    with pytest.raises(AuthConfigurationError, match="SECRET_KEY") as captured:
        sso._session_secret()

    assert weak_secret not in str(captured.value)


def test_sso_factory_accepts_strong_configured_session_secret(monkeypatch):
    sso = _sso_module()
    configured_secret = "strong-configured-secret-with-entropy-123456789"
    monkeypatch.setenv("SECRET_KEY", configured_secret)

    assert sso._session_secret() == configured_secret


def test_packaged_launcher_dispatches_sso_to_uvicorn(monkeypatch, tmp_path):
    sso = _sso_module()
    mara_app = object()
    fastapi_app = SimpleNamespace(
        state=SimpleNamespace(
            mara_app=mara_app,
            launch_config=_launch_config(host="0.0.0.0"),
        )
    )
    calls = []
    factory_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(launcher.flowsettings, "MARA_AUTH_MODE", "sso", raising=False)
    monkeypatch.setattr(launcher.flowsettings, "KH_SSO_ENABLED", False, raising=False)
    monkeypatch.setattr(
        launcher,
        "prepare_launch",
        lambda **_kwargs: pytest.fail("SSO policy belongs to the SSO factory"),
    )

    def _create_sso_app(**kwargs):
        factory_calls.append(kwargs)
        return fastapi_app

    monkeypatch.setattr(sso, "create_sso_app", _create_sso_app)
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
    assert factory_calls == [{"host": "0.0.0.0", "share": None}]
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
