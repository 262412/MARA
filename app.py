import os
from pathlib import Path

from theflow.settings import settings as flowsettings

from ktem.assets import ASSETS_DIR
from ktem.launcher import ensure_gradio_temp_dir

KH_APP_DATA_DIR = getattr(flowsettings, "KH_APP_DATA_DIR", ".")
KH_GRADIO_SHARE = getattr(flowsettings, "KH_GRADIO_SHARE", False)
KH_FILESTORAGE_PATH = getattr(
    flowsettings, "KH_FILESTORAGE_PATH", os.path.join(KH_APP_DATA_DIR, "user_data", "files")
)
GRADIO_TEMP_DIR = os.getenv("GRADIO_TEMP_DIR", None)
# override GRADIO_TEMP_DIR if it's not set
if GRADIO_TEMP_DIR is None:
    GRADIO_TEMP_DIR = ensure_gradio_temp_dir()

Path(KH_FILESTORAGE_PATH).mkdir(parents=True, exist_ok=True)


from ktem.main import App  # noqa

app = App()
demo = app.make()
demo.queue().launch(
    favicon_path=app._favicon,
    inbrowser=True,
    allowed_paths=[
        str(ASSETS_DIR),
        GRADIO_TEMP_DIR,
        KH_FILESTORAGE_PATH,
    ],
    share=KH_GRADIO_SHARE,
)
