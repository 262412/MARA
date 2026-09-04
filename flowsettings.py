import os
from pathlib import Path

from ktem.runtime_bootstrap import get_runtime_paths
from ktem.runtime_defaults import build_kotaemon_settings
from theflow.settings.default import *  # noqa

this_dir = Path(__file__).resolve().parent
app_data_dir = Path(
    os.environ.get("KH_APP_DATA_DIR", this_dir / "ktem_app_data")
).expanduser()

globals().update(
    build_kotaemon_settings(
        base_dir=this_dir,
        app_data_dir=app_data_dir,
        docs_dir=this_dir / "docs",
        mode="dev",
    )
)

STORAGE = {
    "__type__": "theflow.storage.LocalStorage",
    "prefix": str(get_runtime_paths().cache_dir / "theflow"),
}

KH_SETTINGS_SOURCE = "workspace-flowsettings"
