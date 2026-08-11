import pytest
from ktem.runtime_defaults import build_kotaemon_settings


@pytest.fixture(autouse=True)
def _clear_auth_environment(monkeypatch):
    for name in (
        "MARA_AUTH_MODE",
        "KH_SSO_ENABLED",
        "KH_FEATURE_USER_MANAGEMENT",
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
    assert settings["KH_FEATURE_USER_MANAGEMENT"] is False
    assert settings["KH_FEATURE_USER_MANAGEMENT_ADMIN"] == ""
    assert settings["KH_FEATURE_USER_MANAGEMENT_PASSWORD"] == ""


@pytest.mark.parametrize(
    ("mode", "expected_user_management"),
    [
        ("auto", False),
        ("local", False),
        ("password", True),
        ("sso", True),
    ],
)
def test_runtime_defaults_derive_user_management_from_canonical_mode(
    monkeypatch,
    tmp_path,
    mode,
    expected_user_management,
):
    monkeypatch.setenv("MARA_AUTH_MODE", mode)
    monkeypatch.setenv("KH_FEATURE_USER_MANAGEMENT", "false")

    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
    )

    assert settings["MARA_AUTH_MODE"] == mode
    assert settings["KH_FEATURE_USER_MANAGEMENT"] is expected_user_management


def test_runtime_defaults_map_safe_legacy_admin_pair_to_password(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("KH_FEATURE_USER_MANAGEMENT", "true")
    monkeypatch.setenv("KH_FEATURE_USER_MANAGEMENT_ADMIN", "Operator")
    monkeypatch.setenv("KH_FEATURE_USER_MANAGEMENT_PASSWORD", "CorrectHorse7!")

    with pytest.warns(DeprecationWarning, match="one minor release"):
        settings = build_kotaemon_settings(
            base_dir=tmp_path,
            app_data_dir=tmp_path / "app-data",
        )

    assert settings["MARA_AUTH_MODE"] == "password"
    assert settings["KH_FEATURE_USER_MANAGEMENT"] is True


def test_empty_legacy_user_management_flag_does_not_enable_network_auth(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("KH_FEATURE_USER_MANAGEMENT", "true")

    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
    )

    assert settings["MARA_AUTH_MODE"] == "auto"
    assert settings["KH_FEATURE_USER_MANAGEMENT"] is False


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


def _config_reader(values):
    def read(name, default=None, cast=None):
        value = values.get(name, default)
        return cast(value) if cast is not None else value

    return read


def test_desktop_runtime_does_not_select_google_or_placeholders(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(tmp_path / "desktop"))

    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
        config_reader=_config_reader({}),
    )

    assert "google" not in settings["KH_LLMS"]
    assert "google" not in settings["KH_EMBEDDINGS"]
    assert not any(model.get("default") for model in settings["KH_LLMS"].values())
    assert not any(model.get("default") for model in settings["KH_EMBEDDINGS"].values())


def test_desktop_provider_defaults_are_independent_for_chat_and_embeddings(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(tmp_path / "desktop"))

    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
        config_reader=_config_reader(
            {
                "OPENAI_API_BASE": "http://127.0.0.1:43123/v1",
                "OPENAI_API_KEY": "configured-key",
                "OPENAI_CHAT_MODEL": "chat-model",
                "OPENAI_EMBEDDINGS_MODEL": "openai-embedding",
                "LOCAL_MODEL_EMBEDDINGS": "ollama-embedding",
            }
        ),
    )

    assert settings["KH_LLMS"]["openai"]["default"] is True
    assert settings["KH_LLMS"]["openai"]["spec"]["model"] == "chat-model"
    assert settings["KH_EMBEDDINGS"]["ollama"]["default"] is True
    assert settings["KH_EMBEDDINGS"]["ollama"]["spec"]["model"] == ("ollama-embedding")
    assert settings["KH_EMBEDDINGS"]["openai"]["default"] is False


def test_desktop_ollama_embedding_can_be_configured_without_chat_model(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(tmp_path / "desktop"))

    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
        config_reader=_config_reader(
            {
                "LOCAL_MODEL_EMBEDDINGS": "nomic-embed-text",
                "KH_OLLAMA_URL": "http://127.0.0.1:11434/v1/",
            }
        ),
    )

    assert "ollama" not in settings["KH_LLMS"]
    assert settings["KH_EMBEDDINGS"]["ollama"]["default"] is True


def test_desktop_openai_uses_its_stable_base_url_when_base_is_omitted(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(tmp_path / "desktop"))

    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
        config_reader=_config_reader({"OPENAI_API_KEY": "configured-key"}),
    )

    assert settings["KH_LLMS"]["openai"]["default"] is True
    assert settings["KH_LLMS"]["openai"]["spec"]["base_url"] == (
        "https://api.openai.com/v1"
    )


def test_desktop_azure_defaults_are_selected_for_each_configured_role(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(tmp_path / "desktop"))

    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
        config_reader=_config_reader(
            {
                "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
                "AZURE_OPENAI_API_KEY": "azure-key",
                "AZURE_OPENAI_CHAT_DEPLOYMENT": "chat-deployment",
                "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT": "embedding-deployment",
            }
        ),
    )

    assert settings["KH_LLMS"]["azure"]["default"] is True
    assert settings["KH_EMBEDDINGS"]["azure"]["default"] is True


def test_desktop_saved_routes_select_chat_and_embedding_independently(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(tmp_path / "desktop"))

    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
        config_reader=_config_reader(
            {
                "MARA_DESKTOP_MODEL_SETTINGS": "1",
                "MARA_DESKTOP_CHAT_PROVIDER": "openai_compatible",
                "MARA_DESKTOP_CHAT_BASE_URL": "https://api.example/v1",
                "MARA_DESKTOP_CHAT_MODEL": "chat-model",
                "MARA_DESKTOP_CHAT_API_KEY": "chat-key",
                "MARA_DESKTOP_EMBEDDING_PROVIDER": "ollama",
                "MARA_DESKTOP_EMBEDDING_BASE_URL": "http://127.0.0.1:11434/v1",
                "MARA_DESKTOP_EMBEDDING_MODEL": "nomic-embed-text",
                "OPENAI_API_KEY": "inherited-key-must-be-ignored",
            }
        ),
    )

    assert settings["KH_LLMS"]["openai"]["default"] is True
    assert settings["KH_LLMS"]["openai"]["spec"]["api_key"] == "chat-key"
    assert settings["KH_EMBEDDINGS"]["ollama"]["default"] is True
    assert settings["KH_EMBEDDINGS"]["ollama"]["spec"]["model"] == ("nomic-embed-text")
    assert "google" not in settings["KH_LLMS"]


def test_desktop_saved_none_routes_do_not_fall_back_to_inherited_providers(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(tmp_path / "desktop"))

    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
        config_reader=_config_reader(
            {
                "MARA_DESKTOP_MODEL_SETTINGS": "1",
                "MARA_DESKTOP_CHAT_PROVIDER": "none",
                "MARA_DESKTOP_EMBEDDING_PROVIDER": "none",
                "OPENAI_API_KEY": "inherited-key-must-be-ignored",
                "LOCAL_MODEL": "inherited-local-model-must-be-ignored",
            }
        ),
    )

    assert settings["KH_LLMS"] == {}
    assert settings["KH_EMBEDDINGS"] == {}


def test_desktop_saved_azure_route_is_explicit_and_provider_specific(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(tmp_path / "desktop"))

    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
        config_reader=_config_reader(
            {
                "MARA_DESKTOP_MODEL_SETTINGS": "1",
                "MARA_DESKTOP_CHAT_PROVIDER": "azure_openai",
                "MARA_DESKTOP_CHAT_BASE_URL": "https://azure.example",
                "MARA_DESKTOP_CHAT_MODEL": "chat-deployment",
                "MARA_DESKTOP_CHAT_API_VERSION": "2024-02-15-preview",
                "MARA_DESKTOP_CHAT_API_KEY": "azure-key",
                "MARA_DESKTOP_EMBEDDING_PROVIDER": "none",
            }
        ),
    )

    spec = settings["KH_LLMS"]["azure"]["spec"]
    assert settings["KH_LLMS"]["azure"]["default"] is True
    assert spec["azure_endpoint"] == "https://azure.example"
    assert spec["azure_deployment"] == "chat-deployment"
    assert spec["api_key"] == "azure-key"
    assert settings["KH_EMBEDDINGS"] == {}


def test_desktop_saved_openai_route_keeps_missing_credentials_visible(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(tmp_path / "desktop"))

    settings = build_kotaemon_settings(
        base_dir=tmp_path,
        app_data_dir=tmp_path / "app-data",
        config_reader=_config_reader(
            {
                "MARA_DESKTOP_MODEL_SETTINGS": "1",
                "MARA_DESKTOP_CHAT_PROVIDER": "openai_compatible",
                "MARA_DESKTOP_CHAT_BASE_URL": "https://api.example/v1",
                "MARA_DESKTOP_CHAT_MODEL": "chat-model",
                "MARA_DESKTOP_EMBEDDING_PROVIDER": "none",
            }
        ),
    )

    assert settings["KH_LLMS"]["openai"]["default"] is True
    assert settings["KH_LLMS"]["openai"]["spec"]["api_key"] == ""
