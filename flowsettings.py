from pathlib import Path

from ktem.runtime_defaults import build_kotaemon_settings
from theflow.settings.default import *  # noqa

this_dir = Path(__file__).resolve().parent

globals().update(
    build_kotaemon_settings(
        base_dir=this_dir,
        app_data_dir=this_dir / "ktem_app_data",
        docs_dir=this_dir / "docs",
        mode="dev",
    )
)

KH_SETTINGS_SOURCE = "workspace-flowsettings"
