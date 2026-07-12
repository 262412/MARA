from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from ktem.runtime_bootstrap import get_runtime_paths, load_packaged_runtime_env
from ktem.runtime_defaults import build_kotaemon_settings
from theflow.settings.default import *  # noqa


def _load_user_overrides(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}

    spec = importlib.util.spec_from_file_location("kotaemon_user_flowsettings", path)
    if spec is None or spec.loader is None:
        return {}

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {name: getattr(module, name) for name in dir(module) if name.isupper()}


runtime_paths = get_runtime_paths()
load_packaged_runtime_env()
app_data_dir = Path(
    os.environ.get("KH_APP_DATA_DIR", runtime_paths.data_dir)
).expanduser()

globals().update(
    build_kotaemon_settings(
        base_dir=runtime_paths.config_dir,
        app_data_dir=app_data_dir,
        docs_dir=runtime_paths.config_dir / "docs",
        mode="package",
    )
)
globals().update(_load_user_overrides(runtime_paths.flowsettings_path))

KH_SETTINGS_SOURCE = "package-default"
KH_RUNTIME_CONFIG_DIR = runtime_paths.config_dir
KH_RUNTIME_DATA_DIR = runtime_paths.data_dir
KH_RUNTIME_CACHE_DIR = runtime_paths.cache_dir
KH_USER_FLOWSETTINGS_PATH = runtime_paths.flowsettings_path
KH_USER_ENV_PATH = runtime_paths.env_path
