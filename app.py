import os
from pathlib import Path


def log_startup(message: str) -> None:
    print(f"[MARA Azure startup] {message}", flush=True)


if os.getenv("WEBSITE_SITE_NAME"):
    os.environ.setdefault("KH_APP_DATA_DIR", "/home/site/mara_data")
    log_startup(
        f"Azure App Service detected; KH_APP_DATA_DIR={os.environ['KH_APP_DATA_DIR']}"
    )

from ktem.assets import ASSETS_DIR  # noqa: E402
from ktem.launcher import ensure_gradio_temp_dir  # noqa: E402
from theflow.settings import settings as flowsettings  # noqa: E402

KH_APP_DATA_DIR = getattr(flowsettings, "KH_APP_DATA_DIR", ".")
KH_GRADIO_SHARE = getattr(flowsettings, "KH_GRADIO_SHARE", False)
KH_FILESTORAGE_PATH = getattr(
    flowsettings,
    "KH_FILESTORAGE_PATH",
    os.path.join(KH_APP_DATA_DIR, "user_data", "files"),
)
KH_DOC_DIR = str(Path(getattr(flowsettings, "KH_DOC_DIR", "docs")).resolve())
GRADIO_TEMP_DIR = os.getenv("GRADIO_TEMP_DIR", None)
server_port = int(os.getenv("PORT", "8000"))
# override GRADIO_TEMP_DIR if it's not set
if GRADIO_TEMP_DIR is None:
    GRADIO_TEMP_DIR = ensure_gradio_temp_dir()

log_startup(f"server_port={server_port}")
log_startup(f"KH_FILESTORAGE_PATH={KH_FILESTORAGE_PATH}")
log_startup(f"GRADIO_TEMP_DIR={GRADIO_TEMP_DIR}")
Path(KH_FILESTORAGE_PATH).mkdir(parents=True, exist_ok=True)


log_startup("Importing ktem.main.App")
from ktem.main import App  # noqa

log_startup("Creating MARA App")
app = App()
log_startup("Building Gradio blocks")
demo = app.make()
log_startup(f"Launching Gradio on 0.0.0.0:{server_port}")
demo.queue().launch(
    favicon_path=app._favicon,
    allowed_paths=[
        str(ASSETS_DIR),
        KH_DOC_DIR,
        GRADIO_TEMP_DIR,
        KH_FILESTORAGE_PATH,
    ],
    share=KH_GRADIO_SHARE,
    server_name="0.0.0.0",
    server_port=server_port,
    inbrowser=False,
)
