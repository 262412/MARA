from __future__ import annotations

import socket

import pytest

from kotaemon import app_init as app_init_module

EXPECTED_PAYLOAD_KEYS = {
    "config_dir",
    "data_dir",
    "cache_dir",
    "flowsettings_path",
    "env_path",
    "env_example_path",
}


def _isolate_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "config"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "runtime" / "ktem_app_data"))


def test_app_init_materializes_pdfjs_offline_without_payload_drift(
    monkeypatch,
    tmp_path,
):
    _isolate_runtime(monkeypatch, tmp_path)

    def _network_forbidden(*_args, **_kwargs):
        raise AssertionError("MARA app init attempted network access")

    monkeypatch.setattr(socket, "create_connection", _network_forbidden)

    payload = app_init_module.write_app_init_files(force=True, auth_mode="local")

    assert set(payload) == EXPECTED_PAYLOAD_KEYS
    pdfjs_dir = tmp_path / "runtime" / "ktem_app_data" / "assets" / "pdfjs" / "6.1.200"
    assert (pdfjs_dir / "LICENSE").is_file()
    assert (pdfjs_dir / "web" / "viewer.html").is_file()


def test_password_init_failure_rolls_back_new_pdfjs_and_config(
    monkeypatch,
    tmp_path,
):
    _isolate_runtime(monkeypatch, tmp_path)
    monkeypatch.setattr(
        app_init_module,
        "preflight_password_admin",
        lambda **_kwargs: None,
    )

    def _fail_provision(**_kwargs):
        raise RuntimeError("synthetic provisioning failure")

    monkeypatch.setattr(app_init_module, "provision_password_admin", _fail_provision)

    with pytest.raises(RuntimeError, match="synthetic provisioning failure"):
        app_init_module.initialize_password_app(
            username="admin",
            password="CorrectHorse7!",
            force=True,
        )

    assert not (tmp_path / "config" / "Kotaemon" / "flowsettings.py").exists()
    pdfjs_dir = tmp_path / "runtime" / "ktem_app_data" / "assets" / "pdfjs" / "6.1.200"
    assert not pdfjs_dir.exists()


def test_password_init_failure_preserves_preexisting_pdfjs(
    monkeypatch,
    tmp_path,
):
    _isolate_runtime(monkeypatch, tmp_path)
    from ktem.assets.pdfjs_assets import materialize_pdfjs

    existing = materialize_pdfjs()
    viewer_before = (existing.path / "web" / "viewer.html").read_bytes()
    monkeypatch.setattr(
        app_init_module,
        "preflight_password_admin",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        app_init_module,
        "provision_password_admin",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("provision failed")),
    )

    with pytest.raises(RuntimeError, match="provision failed"):
        app_init_module.initialize_password_app(
            username="admin",
            password="CorrectHorse7!",
            force=True,
        )

    assert (existing.path / "web" / "viewer.html").read_bytes() == viewer_before
    assert existing.path.is_dir()
