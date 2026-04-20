from __future__ import annotations

import os
from pathlib import Path

from theflow.settings import settings as flowsettings

from ktem.assets import ASSETS_DIR
from ktem.main import App


def ensure_gradio_temp_dir() -> str:
    gradio_temp_dir = os.getenv("GRADIO_TEMP_DIR", "").strip()
    if not gradio_temp_dir:
        app_data_dir = Path(getattr(flowsettings, "KH_APP_DATA_DIR", Path.cwd()))
        gradio_temp_dir = str((app_data_dir / "gradio_tmp").resolve())
        os.environ["GRADIO_TEMP_DIR"] = gradio_temp_dir

    Path(gradio_temp_dir).mkdir(parents=True, exist_ok=True)
    return gradio_temp_dir


def launch_app(
    *,
    host: str | None = None,
    port: int | None = None,
    share: bool | None = None,
    inbrowser: bool = True,
):
    file_storage_path = Path(
        getattr(flowsettings, "KH_FILESTORAGE_PATH", Path.cwd() / "user_data" / "files")
    )
    file_storage_path.mkdir(parents=True, exist_ok=True)

    gradio_temp_dir = ensure_gradio_temp_dir()
    app = App()
    demo = app.make()
    demo.queue().launch(
        favicon_path=app._favicon,
        inbrowser=inbrowser,
        allowed_paths=[
            str(ASSETS_DIR),
            gradio_temp_dir,
            str(file_storage_path),
        ],
        share=getattr(flowsettings, "KH_GRADIO_SHARE", False)
        if share is None
        else share,
        server_name=host,
        server_port=port,
    )
    return app
