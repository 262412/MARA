"""Package-owned SSO application factory."""

from __future__ import annotations

from pathlib import Path

import gradiologin
from decouple import config
from fastapi import FastAPI
from fastapi.responses import FileResponse
from ktem.assets import ASSETS_DIR
from ktem.auth.policy import AuthConfigurationError
from ktem.launcher import LaunchConfig, ensure_gradio_temp_dir, prepare_launch
from ktem.main import App
from theflow.settings import settings as flowsettings


def _register_provider() -> None:
    authentication_method = str(config("AUTHENTICATION_METHOD", "GOOGLE")).upper()
    if authentication_method == "KEYCLOAK":
        server_url = config("KEYCLOAK_SERVER_URL", default="")
        realm = config("KEYCLOAK_REALM", default="")
        gradiologin.register(
            name="keycloak",
            server_metadata_url=(
                f"{server_url}/realms/{realm}/.well-known/openid-configuration"
            ),
            client_id=config("KEYCLOAK_CLIENT_ID", default=""),
            client_secret=config("KEYCLOAK_CLIENT_SECRET", default=""),
            client_kwargs={"scope": "openid email profile"},
        )
        return

    gradiologin.register(
        name="google",
        server_metadata_url=(
            "https://accounts.google.com/.well-known/openid-configuration"
        ),
        client_id=config("GOOGLE_CLIENT_ID", default=""),
        client_secret=config("GOOGLE_CLIENT_SECRET", default=""),
        client_kwargs={"scope": "openid email profile"},
    )


def create_sso_app(
    *,
    host: str | None = None,
    launch_config: LaunchConfig | None = None,
) -> FastAPI:
    """Build the FastAPI/gradiologin app after the shared pre-bind policy."""
    resolved = launch_config or prepare_launch(host=host)
    if resolved.auth_mode != "sso":
        raise AuthConfigurationError(
            "The SSO application factory requires MARA_AUTH_MODE=sso."
        )

    gradio_temp_dir = ensure_gradio_temp_dir()
    file_storage_path = Path(
        getattr(
            flowsettings,
            "KH_FILESTORAGE_PATH",
            Path.cwd() / "user_data" / "files",
        )
    )
    doc_dir = Path(getattr(flowsettings, "KH_DOC_DIR", Path.cwd() / "docs")).resolve()
    file_storage_path.mkdir(parents=True, exist_ok=True)

    mara_app = App()
    blocks = mara_app.make()
    app = FastAPI()
    app.state.mara_app = mara_app
    _register_provider()

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(mara_app._favicon)

    return gradiologin.mount_gradio_app(
        app,
        blocks,
        "/app",
        secret_key=config("SECRET_KEY", default="some-secret-string"),
        allowed_paths=[
            str(ASSETS_DIR),
            str(doc_dir),
            gradio_temp_dir,
            str(file_storage_path),
        ],
    )
