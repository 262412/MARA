from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ktem.app_server import resolve_gradio_server_port
from ktem.assets import ASSETS_DIR
from ktem.auth.policy import resolve_auth_mode, resolve_legacy_bootstrap_credentials
from ktem.auth.service import authenticate_password, validate_password_admin_readiness
from ktem.main import App
from theflow.settings import settings as flowsettings


@dataclass(frozen=True)
class LaunchConfig:
    auth_mode: str
    host: str
    auth: Callable[[str, str], bool] | None


def _resolve_launch_host(host: str | None) -> str:
    return str(host or os.getenv("GRADIO_SERVER_NAME") or "127.0.0.1").strip()


def prepare_launch(*, host: str | None = None, settings=flowsettings) -> LaunchConfig:
    """Resolve authentication and validate policy before a server can bind."""
    effective_host = _resolve_launch_host(host)
    configured_mode = getattr(settings, "MARA_AUTH_MODE", None)
    legacy_sso_enabled = bool(getattr(settings, "KH_SSO_ENABLED", False))
    if configured_mode is None and not legacy_sso_enabled:
        legacy_credentials = resolve_legacy_bootstrap_credentials(settings)
        if legacy_credentials is not None:
            configured_mode = "password"

    auth_mode = resolve_auth_mode(
        configured_mode=configured_mode,
        host=effective_host,
        legacy_sso_enabled=legacy_sso_enabled,
    )
    settings.KH_FEATURE_USER_MANAGEMENT = auth_mode in {"password", "sso"}

    auth = None
    if auth_mode == "password":
        validate_password_admin_readiness()
        auth = authenticate_password

    return LaunchConfig(auth_mode=auth_mode, host=effective_host, auth=auth)


def ensure_gradio_temp_dir() -> str:
    gradio_temp_dir = os.getenv("GRADIO_TEMP_DIR", "").strip()
    if not gradio_temp_dir:
        app_data_dir = Path(getattr(flowsettings, "KH_APP_DATA_DIR", Path.cwd()))
        gradio_temp_dir = str((app_data_dir / "gradio_tmp").resolve())
        os.environ["GRADIO_TEMP_DIR"] = gradio_temp_dir

    Path(gradio_temp_dir).mkdir(parents=True, exist_ok=True)
    return gradio_temp_dir


def _launch_sso_app(launch_config: LaunchConfig, port: int | None):
    import uvicorn
    from ktem.sso import create_sso_app

    fastapi_app = create_sso_app(launch_config=launch_config)
    uvicorn.run(
        fastapi_app,
        host=launch_config.host,
        port=resolve_gradio_server_port(port),
    )
    return fastapi_app.state.mara_app


def launch_app(
    *,
    host: str | None = None,
    port: int | None = None,
    share: bool | None = None,
    inbrowser: bool = True,
):
    launch_config = prepare_launch(host=host)
    if launch_config.auth_mode == "sso":
        return _launch_sso_app(launch_config, port)

    file_storage_path = Path(
        getattr(flowsettings, "KH_FILESTORAGE_PATH", Path.cwd() / "user_data" / "files")
    )
    doc_dir = Path(getattr(flowsettings, "KH_DOC_DIR", Path.cwd() / "docs")).resolve()
    file_storage_path.mkdir(parents=True, exist_ok=True)

    gradio_temp_dir = ensure_gradio_temp_dir()
    app = App()
    demo = app.make()
    demo.queue().launch(
        favicon_path=app._favicon,
        inbrowser=inbrowser,
        allowed_paths=[
            str(ASSETS_DIR),
            str(doc_dir),
            gradio_temp_dir,
            str(file_storage_path),
        ],
        share=getattr(flowsettings, "KH_GRADIO_SHARE", False)
        if share is None
        else share,
        server_name=launch_config.host,
        server_port=resolve_gradio_server_port(port),
        auth=launch_config.auth,
    )
    return app
