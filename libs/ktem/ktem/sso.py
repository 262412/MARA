"""Package-owned SSO application factory."""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from pathlib import Path

import gradiologin
from decouple import config
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from ktem.assets import ASSETS_DIR
from ktem.auth.policy import AuthConfigurationError
from ktem.launcher import (
    ensure_gradio_temp_dir,
    ensure_pdfjs_runtime_assets,
    prepare_launch,
)
from ktem.main import App
from theflow.settings import settings as flowsettings

_GENERATED_SESSION_SECRET = secrets.token_urlsafe(48)
_KNOWN_WEAK_SESSION_SECRETS = frozenset({"some-secret-string", "default-secret-key"})
_MIN_SESSION_SECRET_LENGTH = 32
_MIN_SESSION_SECRET_DISTINCT_CHARS = 8


def _session_secret() -> str:
    configured_secret = str(config("SECRET_KEY", default="") or "").strip()
    if not configured_secret:
        return _GENERATED_SESSION_SECRET
    if (
        configured_secret.casefold() in _KNOWN_WEAK_SESSION_SECRETS
        or len(configured_secret) < _MIN_SESSION_SECRET_LENGTH
        or len(set(configured_secret)) < _MIN_SESSION_SECRET_DISTINCT_CHARS
    ):
        raise AuthConfigurationError(
            "SECRET_KEY must be at least 32 characters with sufficient entropy "
            "and must not use a known default."
        )
    return configured_secret


def sso_auth_dependency(request: Request) -> str | None:
    """Return the stable subject from a signed gradiologin provider session."""
    claim = request.session.get("user")
    if not isinstance(claim, Mapping):
        return None
    subject = str(claim.get("sub") or "").strip()
    email = str(claim.get("email") or "").strip()
    return subject if subject and email else None


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
    share: bool | None = None,
) -> FastAPI:
    """Build the FastAPI/gradiologin app after the shared pre-bind policy."""
    resolved = prepare_launch(host=host, share=share)
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
    pdfjs_dir = ensure_pdfjs_runtime_assets(settings=flowsettings)

    mara_app = App()
    blocks = mara_app.make()
    app = FastAPI()
    app.state.mara_app = mara_app
    app.state.launch_config = resolved
    _register_provider()

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(mara_app._favicon)

    return gradiologin.mount_gradio_app(
        app,
        blocks,
        "/app",
        secret_key=_session_secret(),
        auth_dependency=sso_auth_dependency,
        allowed_paths=[
            str(ASSETS_DIR),
            str(pdfjs_dir),
            str(doc_dir),
            gradio_temp_dir,
            str(file_storage_path),
        ],
    )
