import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest
from ktem import launcher
from ktem.auth.policy import AuthConfigurationError

REPO_ROOT = Path(__file__).resolve().parents[3]


def _settings(mode):
    return SimpleNamespace(
        MARA_AUTH_MODE=mode,
        KH_SSO_ENABLED=False,
        KH_FEATURE_USER_MANAGEMENT=mode in {"password", "sso"},
        KH_FEATURE_USER_MANAGEMENT_ADMIN="",
        KH_FEATURE_USER_MANAGEMENT_PASSWORD="",
    )


def _prepare_launch(*, mode, host, monkeypatch, settings=None, share=None):
    assert hasattr(
        launcher, "prepare_launch"
    ), "ktem.launcher.prepare_launch must be the single pre-bind policy seam"
    monkeypatch.setattr(
        launcher,
        "validate_password_admin_readiness",
        lambda: None,
        raising=False,
    )
    kwargs = {"host": host, "settings": settings or _settings(mode)}
    if share is not None:
        kwargs["share"] = share
    return launcher.prepare_launch(**kwargs)


@pytest.mark.parametrize("mode", ["auto", "local"])
def test_prebind_policy_rejects_non_loopback_local_modes(monkeypatch, mode):
    with pytest.raises(AuthConfigurationError, match="cannot bind"):
        _prepare_launch(mode=mode, host="0.0.0.0", monkeypatch=monkeypatch)


@pytest.mark.parametrize("mode", ["auto", "local"])
def test_local_launch_disables_user_management_and_server_auth(monkeypatch, mode):
    settings = _settings(mode)
    settings.KH_FEATURE_USER_MANAGEMENT = True
    config = _prepare_launch(
        mode=mode,
        host="127.0.0.1",
        monkeypatch=monkeypatch,
        settings=settings,
    )

    assert config.auth_mode == mode
    assert config.host == "127.0.0.1"
    assert config.auth is None
    assert config.share is False
    assert settings.KH_FEATURE_USER_MANAGEMENT is False
    assert settings.MARA_AUTH_MODE == mode


def test_password_launch_selects_gradio_server_auth(monkeypatch):
    settings = _settings("password")
    readiness_calls = []
    monkeypatch.setattr(
        launcher,
        "validate_password_admin_readiness",
        lambda: readiness_calls.append(True),
        raising=False,
    )
    assert hasattr(launcher, "prepare_launch")

    config = launcher.prepare_launch(
        host="0.0.0.0",
        settings=settings,
    )

    from ktem.auth.service import authenticate_password

    assert config.auth_mode == "password"
    assert config.auth is authenticate_password
    assert config.share is False
    assert settings.KH_FEATURE_USER_MANAGEMENT is True
    assert settings.MARA_AUTH_MODE == "password"
    assert readiness_calls == [True]


def test_sso_launch_enables_management_without_gradio_password_auth(monkeypatch):
    settings = _settings("sso")
    settings.KH_FEATURE_USER_MANAGEMENT = False

    config = _prepare_launch(
        mode="sso",
        host="0.0.0.0",
        monkeypatch=monkeypatch,
        settings=settings,
    )

    assert config.auth_mode == "sso"
    assert config.auth is None
    assert config.share is False
    assert settings.KH_FEATURE_USER_MANAGEMENT is True
    assert settings.MARA_AUTH_MODE == "sso"


def test_local_launch_rejects_gradio_share(monkeypatch):
    assert "share" in inspect.signature(launcher.prepare_launch).parameters
    with pytest.raises(AuthConfigurationError, match="share.*password.*sso"):
        _prepare_launch(
            mode="local",
            host="127.0.0.1",
            share=True,
            monkeypatch=monkeypatch,
        )


def test_local_launch_rejects_share_enabled_in_flowsettings(monkeypatch):
    settings = _settings("local")
    settings.KH_GRADIO_SHARE = True

    with pytest.raises(AuthConfigurationError, match="share.*password.*sso"):
        _prepare_launch(
            mode="local",
            host="127.0.0.1",
            monkeypatch=monkeypatch,
            settings=settings,
        )


def test_password_launch_allows_gradio_share(monkeypatch):
    assert "share" in inspect.signature(launcher.prepare_launch).parameters
    config = _prepare_launch(
        mode="password",
        host="127.0.0.1",
        share=True,
        monkeypatch=monkeypatch,
    )

    assert config.share is True


def test_legacy_sso_mapping_propagates_canonical_mode(monkeypatch):
    settings = SimpleNamespace(
        KH_SSO_ENABLED=True,
        KH_FEATURE_USER_MANAGEMENT=False,
        KH_FEATURE_USER_MANAGEMENT_ADMIN="",
        KH_FEATURE_USER_MANAGEMENT_PASSWORD="",
        KH_GRADIO_SHARE=False,
    )

    with pytest.warns(DeprecationWarning, match="KH_SSO_ENABLED"):
        config = _prepare_launch(
            mode=None,
            host="0.0.0.0",
            monkeypatch=monkeypatch,
            settings=settings,
        )

    assert config.auth_mode == "sso"
    assert settings.MARA_AUTH_MODE == "sso"
    assert settings.KH_FEATURE_USER_MANAGEMENT is True


def test_legacy_admin_mapping_propagates_canonical_mode(monkeypatch):
    settings = SimpleNamespace(
        KH_SSO_ENABLED=False,
        KH_FEATURE_USER_MANAGEMENT=False,
        KH_FEATURE_USER_MANAGEMENT_ADMIN="LegacyOperator",
        KH_FEATURE_USER_MANAGEMENT_PASSWORD="CorrectHorse7!",
        KH_GRADIO_SHARE=False,
    )

    with pytest.warns(DeprecationWarning, match="one minor release"):
        config = _prepare_launch(
            mode=None,
            host="0.0.0.0",
            monkeypatch=monkeypatch,
            settings=settings,
        )

    assert config.auth_mode == "password"
    assert settings.MARA_AUTH_MODE == "password"
    assert settings.KH_FEATURE_USER_MANAGEMENT is True


def test_environment_host_is_validated_when_cli_host_is_absent(monkeypatch):
    monkeypatch.setenv("GRADIO_SERVER_NAME", "0.0.0.0")

    with pytest.raises(AuthConfigurationError, match="cannot bind"):
        _prepare_launch(mode="auto", host=None, monkeypatch=monkeypatch)


def test_gradio_launch_receives_selected_password_auth(monkeypatch, tmp_path):
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

    config = SimpleNamespace(
        auth_mode="password",
        host="127.0.0.1",
        auth=lambda username, password: True,
        share=True,
    )
    monkeypatch.setattr(launcher, "prepare_launch", lambda **_kwargs: config)
    monkeypatch.setattr(launcher, "App", _App)
    monkeypatch.setattr(launcher, "ASSETS_DIR", tmp_path)
    monkeypatch.setattr(launcher, "ensure_gradio_temp_dir", lambda: str(tmp_path))
    monkeypatch.setattr(
        launcher,
        "flowsettings",
        SimpleNamespace(
            KH_APP_DATA_DIR=tmp_path,
            KH_DOC_DIR=tmp_path,
            KH_FILESTORAGE_PATH=tmp_path,
            KH_GRADIO_SHARE=False,
        ),
    )

    launcher.launch_app(host="127.0.0.1", port=7860, inbrowser=False)

    assert launched["server_name"] == "127.0.0.1"
    assert launched["auth"] is config.auth
    assert launched["share"] is True


def test_source_app_delegates_to_policy_aware_packaged_launcher():
    source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")

    assert "from ktem.launcher import launch_app" in source
    assert "launch_app(" in source
    assert ".launch(" not in source
