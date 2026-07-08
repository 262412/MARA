from ktem.app_server import DEFAULT_GRADIO_SERVER_PORT, resolve_gradio_server_port


def test_resolve_gradio_server_port_defaults_to_local_gradio_port(monkeypatch):
    monkeypatch.delenv("GRADIO_SERVER_PORT", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    assert resolve_gradio_server_port() == DEFAULT_GRADIO_SERVER_PORT
    assert resolve_gradio_server_port() == 7860


def test_resolve_gradio_server_port_prefers_explicit_argument(monkeypatch):
    monkeypatch.setenv("GRADIO_SERVER_PORT", "7861")
    monkeypatch.setenv("PORT", "8000")

    assert resolve_gradio_server_port(9000) == 9000


def test_resolve_gradio_server_port_prefers_gradio_env_over_platform_port(
    monkeypatch,
):
    monkeypatch.setenv("GRADIO_SERVER_PORT", "7861")
    monkeypatch.setenv("PORT", "8000")

    assert resolve_gradio_server_port() == 7861


def test_resolve_gradio_server_port_uses_platform_port_when_gradio_env_missing(
    monkeypatch,
):
    monkeypatch.delenv("GRADIO_SERVER_PORT", raising=False)
    monkeypatch.setenv("PORT", "8000")

    assert resolve_gradio_server_port() == 8000
