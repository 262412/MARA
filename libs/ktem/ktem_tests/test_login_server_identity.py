from pathlib import Path
from types import SimpleNamespace

import gradio as gr
from ktem.pages import login as login_module

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_login_page_ignores_browser_credentials_for_identity(monkeypatch):
    calls = []

    def _resolve_request_user_id(request, *, auth_mode):
        calls.append((request, auth_mode))
        return "server-resolved-user-id"

    monkeypatch.setattr(
        login_module,
        "resolve_request_user_id",
        _resolve_request_user_id,
        raising=False,
    )
    monkeypatch.setattr(
        login_module,
        "flowsettings",
        SimpleNamespace(MARA_AUTH_MODE="password"),
        raising=False,
    )
    page = object.__new__(login_module.LoginPage)
    request = gr.Request(username="ServerUser")

    result = page.login("BrowserUser", "BrowserPassword", request)

    assert result == ("server-resolved-user-id", "ServerUser", "")
    assert calls == [(request, "password")]


def test_login_page_browser_scripts_never_persist_passwords():
    source = (REPO_ROOT / "libs/ktem/ktem/pages/login.py").read_text(encoding="utf-8")

    assert "getStorage('password'" not in source
    assert 'getStorage("password"' not in source
    assert "setStorage('password'" not in source
    assert 'setStorage("password"' not in source
    assert "localStorage" not in source or "password" not in source
    assert "setStorage('username'" in source


def test_password_logout_uses_gradio_logout_without_password_storage():
    source = (REPO_ROOT / "libs/ktem/ktem/pages/settings.py").read_text(
        encoding="utf-8"
    )

    assert "removeFromStorage('password'" not in source
    assert 'removeFromStorage("password"' not in source
    assert 'window.location.href = "/logout"' in source


def test_login_page_preserves_public_event_and_component_attributes():
    source = (REPO_ROOT / "libs/ktem/ktem/pages/login.py").read_text(encoding="utf-8")

    assert 'public_events = ["onSignIn"]' in source
    for attribute in ("self.usn", "self.pwd", "self.btn_login"):
        assert attribute in source
    assert ").then(\n            self.toggle_login_visibility" in source
    assert "onSignIn = onSignIn.success(**event)" in source
