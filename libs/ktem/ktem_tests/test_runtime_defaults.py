import pytest

from ktem.runtime_defaults import build_kotaemon_settings


@pytest.fixture(autouse=True)
def _clear_auth_environment(monkeypatch):
    for name in (
        "MARA_AUTH_MODE",
        "KH_SSO_ENABLED",
        "KH_FEATURE_USER_MANAGEMENT_ADMIN",
        "KH_FEATURE_USER_MANAGEMENT_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)


def test_runtime_defaults_use_local_multilingual_reranker_by_default(tmp_path):
    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
    )

    assert settings["KH_RERANKINGS"]["local"]["default"] is True
    assert settings["KH_RERANKINGS"]["local"]["spec"] == {
        "__type__": "kotaemon.rerankings.LocalMultilingualReranking"
    }
    assert settings["KH_RERANKINGS"]["cohere"]["default"] is False
    assert (
        settings["KH_OFFICE_PDF_CACHE_DIR"]
        == (tmp_path / "app-data" / "office_pdf_cache_dir").resolve()
    )
    assert settings["KH_OFFICE_TO_PDF_INDEXING"] is True
    assert settings["KH_OFFICE_TO_PDF_INDEXING_STRICT"] is True


def test_runtime_defaults_register_mara_reasoning_mode(tmp_path):
    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
    )

    assert "ktem.reasoning.mara.MaraAgentPipeline" in settings["KH_REASONINGS"]


def test_runtime_defaults_use_mara_public_app_name(tmp_path):
    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
    )

    assert settings["KH_APP_NAME"] == "MARA"


def test_runtime_defaults_use_mara_package_name(tmp_path):
    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
    )

    assert settings["KH_PACKAGE_NAME"] == "mara-app"


def test_runtime_defaults_use_safe_local_auth_defaults(tmp_path):
    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
    )

    assert settings["MARA_AUTH_MODE"] == "auto"
    assert settings["KH_SSO_ENABLED"] is False
    assert settings["KH_FEATURE_USER_MANAGEMENT_ADMIN"] == ""
    assert settings["KH_FEATURE_USER_MANAGEMENT_PASSWORD"] == ""


def test_runtime_defaults_map_legacy_sso_to_canonical_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("KH_SSO_ENABLED", "true")

    with pytest.warns(DeprecationWarning, match="KH_SSO_ENABLED"):
        settings = build_kotaemon_settings(
            base_dir=tmp_path,
            app_data_dir=tmp_path / "app-data",
        )

    assert settings["MARA_AUTH_MODE"] == "sso"
    assert settings["KH_SSO_ENABLED"] is True


def test_runtime_defaults_prefer_canonical_mode_over_legacy_sso(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("MARA_AUTH_MODE", "password")
    monkeypatch.setenv("KH_SSO_ENABLED", "true")

    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
    )

    assert settings["MARA_AUTH_MODE"] == "password"
    assert settings["KH_SSO_ENABLED"] is False
